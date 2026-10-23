# QLDSV desktop application

Ứng dụng desktop Python/PySide6 cho đồ án Quản lý điểm sinh viên. Database development được đóng gói bằng Docker để mọi thành viên clone repository và dựng lại cùng một SQL Server + schema + Stored Procedure + seed data.

## Trạng thái kiến trúc

- Epic 1.1: 5 bảng cốt lõi `Lop`, `Sinhvien`, `Giangvien`, `Monhoc`, `Diem`.
- Repository có thêm bảng bổ trợ `PhanCong` để map `Giangvien - Lop - Monhoc`.
- Epic 1.2: common Stored Procedure `SP-01 -> SP-09`.
- `dbo.TaiKhoan` đã bị loại khỏi kiến trúc mục tiêu. Docker **không** chạy `CreateTaiKhoan.sql` hoặc `seedTaiKhoan.sql`.
- Epic 1.3 bootstrap Login/User/Role; Epic 1.4 cung cấp security SP và ủy quyền tạo account qua server role kỹ thuật.
- Epic 1.5 đã triển khai Login bằng SQL credential người dùng nhập; identity/role lấy từ `sp_ThongTinDangNhap`, không đọc `dbo.TaiKhoan` để xác thực.
- Epic 1.6 đã migrate danh sách/tạo/xóa account sang SQL Login/User/Role metadata và security SP; đổi mật khẩu còn chờ Epic 1.7.

Xem `AGENTS.md` và `specs/README.md` trước khi triển khai ticket mới.

## Yêu cầu

- Docker Desktop với Docker Compose.
- Python 3.10 trở lên để chạy ứng dụng desktop.
- Microsoft ODBC Driver 17 hoặc 18 for SQL Server để PySide6/pyodbc kết nối database.
- SSMS là tùy chọn nhưng nên dùng để kiểm tra Login/User/Role và quyền trực tiếp trong SQL Server.

## Dựng SQL Server + QLDSV bằng Docker

### 1. Tạo file môi trường

Trong PowerShell tại thư mục repository:

```powershell
Copy-Item .env.example .env
```

Mở `.env` và đổi `MSSQL_SA_PASSWORD` và placeholder `QLDSV_ADMIN_PASSWORD` thành password local đủ mạnh trước lần bootstrap đầu. File `.env` đã nằm trong `.gitignore`, không push password thật lên GitHub.

Mặc định SQL Server container được expose ở:

```text
localhost,14330
```

Port này tránh đụng SQL Server local thường dùng `1433`. Có thể đổi `MSSQL_PORT` trong `.env` nếu cần.

### 2. Build và khởi động

```powershell
docker compose up -d --build
```

Compose tạo hai service:

- `sqlserver`: SQL Server 2022 Developer, lưu data trong named volume `qldsv_sql_data`.
- `db-init`: one-shot container chờ SQL Server healthy rồi bootstrap database.

SQL scripts được chạy theo thứ tự:

```text
1. Database_QLDSV.sql
2. CreatePhanCong.sql
3. storedProcedure.sql
4. seedData.sql
5. Security.sql                    (bắt buộc, Epic 1.3)
6. StoredProcedures_Security.sql   (Epic 1.4, chạy qua hook hiện có)
```

`CreateTaiKhoan.sql` và `seedTaiKhoan.sql` được giữ như legacy source hiện tại nhưng **không nằm trong bootstrap Docker**, nên `dbo.TaiKhoan` không bị tạo lại.

### 3. Kiểm tra bootstrap

```powershell
docker compose ps
docker compose logs db-init
```

`db-init` phải kết thúc với exit code `0` và log:

```text
[db-init] QLDSV initialization completed successfully.
```

Trong SSMS có thể kết nối:

```text
Server name: localhost,14330
Authentication: SQL Server Authentication
Login: sa
Password: giá trị MSSQL_SA_PASSWORD trong .env
```

`sa` chỉ dùng để bootstrap/kiểm tra môi trường Docker. Ứng dụng mục tiêu không dùng chung `sa` hoặc một privileged DB account cho người dùng cuối.

## Epic 1.3 — SQL Server Security

`Security.sql` kiểm tra SQL Authentication/Mixed Mode rồi tạo Login trước User, xác minh SID, tạo đúng ba business role owned by dbo và cấp quyền tại SQL Server. Target SQL Server 2022; không tạo `dbo.TaiKhoan`. Nếu principal có type/SID/mapping, ownership hoặc membership xung đột, bootstrap báo lỗi và rollback thay vì tự remap, đổi owner hoặc nâng quyền Student.

Biến môi trường **chỉ dùng lúc init**, được truyền cho service `db-init`:

| Biến | Giá trị mặc định / yêu cầu |
|---|---|
| `QLDSV_ADMIN_LOGIN` | `GV00000001` |
| `QLDSV_ADMIN_PASSWORD` | Bắt buộc khi tạo Admin Login lần đầu; dùng password mạnh, policy ON. Giá trị trong `.env.example` chỉ là placeholder. Có thể bỏ trống khi Login đã tồn tại. |
| `QLDSV_STUDENT_LOGIN` | `SV00000001`; phải trùng `Sinhvien.MASV` có sẵn sau seed |

Docker Compose cũng nhận các biến này từ môi trường process. Bootstrap mã hóa input thành UTF-16LE hex trước khi SQLCMD substitution để tránh SQL injection từ tên/password; hex vẫn là dữ liệu nhạy cảm, không bật echo input (`sqlcmd -e`) hoặc shell tracing. Password không được truyền trong command arguments hoặc in ra log.

Login có sẵn **không bị tạo lại, reset password hoặc đổi password policy**, kể cả khi chạy lại `docker compose up -d --build` với giá trị init khác. Student mới có password `123456`, `CHECK_POLICY=OFF` theo đề; Admin/GiangVien dùng CHECK_POLICY=ON. Mỗi User chỉ thuộc đúng một trong ba business role.

| Quyền | Admin | GiangVien | Student |
|---|---|---|---|
| Kết nối `QLDSV` | GRANT CONNECT | GRANT CONNECT | GRANT CONNECT |
| Database | GRANT CONTROL ON DATABASE::QLDSV | DENY SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo | DENY SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo |
| SP-01..SP-09 | Được thực thi qua CONTROL | DENY EXECUTE từng procedure | DENY EXECUTE từng procedure |
| Server | Member `QLDSV_ACCOUNT_ADMIN` và `dbcreator` | Không server role/quyền quản trị | Không server role/quyền quản trị |
| Safe SP | EXECUTE qua CONTROL (SP điểm yêu cầu Student) | Chỉ `sp_ThongTinDangNhap` | `sp_ThongTinDangNhap`, `sp_SinhVien_XemDiem` |

`QLDSV_ACCOUNT_ADMIN` là **server role kỹ thuật**, không phải business database role. Role có `ALTER ANY LOGIN` và `ALTER ON SERVER ROLE::QLDSV_ACCOUNT_ADMIN` trên chính nó để Admin hợp lệ ủy quyền membership cho Admin mới; `dbcreator` phục vụ Restore và thành viên của nó có thể thêm/bỏ thành viên cùng role. Bootstrap chuyển direct grant `ALTER ANY LOGIN` cũ sang quyền kế thừa từ technical role. Không cấp `sysadmin`, `securityadmin`, `CONTROL SERVER`, `ALTER ANY SERVER ROLE` toàn server hoặc nest custom role vào `db_owner`. Student không được GRANT/DENY EXECUTE toàn schema `dbo`; safe SP dùng static SQL cùng owner hoạt động qua ownership chaining.

GiangVien được tạo từ Account Management với MAGV có sẵn, không có server admin roles; chỉ identity SP, không account/backup/direct CRUD.

Kết nối SSMS bằng **SQL Server Authentication**, server `localhost,14330`, database `QLDSV`:

- Admin: Login `GV00000001` (hoặc biến cấu hình), password đã cung cấp khi tạo Login lần đầu hoặc password hiện tại sau khi đổi.
- Student: Login `SV00000001` (hoặc MASV cấu hình), password ban đầu `123456`; sau khi đổi phải dùng password hiện tại.

Trong SSMS, xem **Security → Logins** ở server và **Databases → QLDSV → Security → Users / Roles → Database Roles**. Kết nối bằng Admin để kiểm tra metadata; dùng chính từng Login để chứng minh quyền:

```sql
USE QLDSV;
SELECT SUSER_SNAME() AS LoginName, USER_NAME() AS DatabaseUser,
       IS_ROLEMEMBER(N'QLDSV_ADMIN') AS IsAdmin,
       IS_ROLEMEMBER(N'QLDSV_GIANGVIEN') AS IsLecturer,
       IS_ROLEMEMBER(N'QLDSV_SINHVIEN') AS IsStudent;
SELECT sp.name AS LoginName, dp.name AS DatabaseUser, r.name AS RoleName
FROM sys.server_principals sp
JOIN sys.database_principals dp ON dp.sid = sp.sid
JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
WHERE r.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN', N'QLDSV_SINHVIEN');
```

Chạy kiểm chứng SEC-07 bằng SQL principals thật trên Docker stack đang chạy (Python standard library + Docker CLI):

```powershell
python docker/verify-security.py
```

Script hỏi kín password Admin hiện tại, hoặc nhận `QLDSV_ADMIN_PASSWORD` từ process. Nếu đã đổi tên Login/password Student, đặt thêm `QLDSV_ADMIN_LOGIN`, `QLDSV_STUDENT_LOGIN`, `QLDSV_STUDENT_PASSWORD` tương ứng. Script không đọc/ghi `.env`. SA chỉ kiểm tra metadata và chạy bootstrap; mọi test quyền Admin đều kết nối bằng Admin Login.

Test gồm identity/role, Student data/SP denials, Admin CRUD/DDL/Login management, Backup/Restore trên **database tạm có tên duy nhất**, và hai lần bootstrap lại. Test tạm đổi password Student để chứng minh bootstrap không reset, rồi phục hồi password ban đầu trong `finally`; nên chạy khi demo Student không có phiên làm việc cần giữ. Object/Login/database/file backup tạm được dọn sau test; không Restore hoặc thay đổi business data của `QLDSV`.

SEC-07 own-score SP được kiểm chứng ở Epic 1.4 dưới đây; Login form dùng credential SQL người dùng đã triển khai ở Epic 1.5.

## Epic 1.4 — Stored Procedures bảo mật

`database/StoredProcedures_Security.sql` target SQL Server 2022 / compatibility level 160, giữ DROP/CREATE style đã kiểm thử và cấp lại object permissions mỗi lần chạy; không tự ALTER compatibility_level. Các SP chạy dưới caller thật, không `EXECUTE AS OWNER`, không `TRUSTWORTHY`, không dùng `dbo.TaiKhoan`.

Application SQL User chỉ có đúng một membership trực tiếp trong `sys.database_role_members`, khớp business role đã xác định và không có database role bổ sung. Cả drift preflight `Security.sql` và runtime `sp_ThongTinDangNhap` đều enforce; thêm role không liên quan sau bootstrap làm authentication từ chối với `52021`. Membership `public` mặc định không phải row trực tiếp được đếm.

| Procedure / chữ ký | Hành vi |
|---|---|
| `sp_TaoTaiKhoan @LoginName nvarchar(max), @Role nvarchar(max), @Password nvarchar(max)=NULL, @CreatedSid varbinary(85)=NULL OUTPUT` | Chỉ Admin; Login → mapped User → business role. Admin/GiangVien phải có MAGV thật, password trống => `Qldsv@123456`, policy ON; chỉ Admin nhận technical role và `dbcreator`; Student phải có MASV thật, password NULL/rỗng ở input rồi server áp `123456`, policy/expiration OFF. Output tùy chọn giữ SID của Login được tạo bởi chính transaction này. |
| `sp_XoaTaiKhoan @LoginName nvarchar(max), @ExpectedSid varbinary(85)=NULL` | Chỉ Admin; kiểm tra mapping/SID, đúng một business role, server membership, ownership; chặn self-delete. Bỏ memberships → DROP USER → DROP LOGIN trong transaction. SID khác ExpectedSid làm từ chối xóa với `52016` và rollback. Login có session hoạt động làm rollback toàn bộ; không KILL session. |
| `sp_ThongTinDangNhap` — không tham số | Một dòng `LoginName`, `DatabaseUser`, `RoleName` (đều `sysname`); suy ra từ SQL connection. Không role, nhiều business role hoặc thêm database role không liên quan đều bị từ chối với `52021`; mapping sai/NULL cũng bị chặn. Staff phải có MAGV, Student phải có MASV thật. |
| `sp_SinhVien_XemDiem` — không tham số | Student-only; `USER_NAME()` là MASV. Trả `MAMH nchar(5)`, `TENMH nvarchar(40)`, `LAN smallint`, `DIEM float NULL`, theo `MAMH, LAN`, raw attempts của chính Student đang học (`NGHIHOC=0`). Không MAX hoặc quy ước mới cho điểm NULL. |

Input dùng `nvarchar(max)` để kiểm tra vượt 128 UTF-16 code units **trước** khi chuyển thành `sysname`; không để SQL tự truncate input. Role chỉ nhận đúng QLDSV_ADMIN, QLDSV_GIANGVIEN, QLDSV_SINHVIEN. Identifier được QUOTENAME, password được escape, lỗi `52000..52099` không chứa password/SQL động. CREATE/DROP principal và thay đổi memberships có TRY/CATCH, XACT_ABORT và rollback; lỗi cũng rollback transaction bên ngoài nếu caller đang mở transaction.

`@CreatedSid` được đặt NULL khi vào procedure, gán sau khi tạo đủ Login/User/roles và trước COMMIT, rồi đặt lại NULL nếu lỗi. Procedure không thêm result set; SQL caller cũ được phép bỏ output parameter. `@ExpectedSid` cũng tùy chọn: UI xóa thông thường không cần truyền, còn tooling/integration cleanup truyền SID đã nhận khi tạo. Delete kiểm tra SID trong transaction trước khi thay đổi memberships và kiểm tra lại ngay trước DROP LOGIN; mismatch `52016` rollback cả User/membership đã thay đổi.

Admin có EXECUTE trên cả bốn SP (SP điểm vẫn yêu cầu Student). GiangVien chỉ có identity SP; account/own-score SP bị DENY. Student bị **DENY EXECUTE** trên `sp_TaoTaiKhoan`, `sp_XoaTaiKhoan`; chỉ được **GRANT EXECUTE** riêng trên `sp_ThongTinDangNhap`, `sp_SinhVien_XemDiem`. Data/schema và common-SP denials từ Epic 1.3 được giữ nguyên. `Security.sql` chỉ chấp nhận CONNECT và hai safe object grants này trong Student preflight.

Kiểm chứng real-principal sau khi bootstrap:

```powershell
python docker/verify-security-procedures.py
python docker/verify-security.py
```

Verifier Epic 1.4 dùng password Admin hiện tại từ process hoặc hidden prompt; từ chối chạy nếu `SV00000002` đã có Login/User để không đụng account có sẵn. Nó tạo Admin tạm gắn disposable Giangvien.MAGV bằng SP, dùng chính Admin mới tạo Student `SV00000002/123456`, kiểm tra raw attempts của MASV seed, SQL identity và các lệnh bị chặn. Test gồm Lecturer identity/data/common-SP/account/own-score denials, staff default/password policy, self-delete, identity không role/dual/triple role, collisions, input/injection, late-failure rollback sau CREATE LOGIN, và giữ một connection Admin tạm để chứng minh DROP LOGIN thất bại rồi rollback cả User/roles. Sau khi tự đóng connection đó, delete thành công. Không KILL session hoặc Restore QLDSV. Principal/object tạm và disposable Giangvien/Sinhvien rows được dọn trong `finally`; seed rows/điểm giữ nguyên.

Verifier rebuild image `db-init` từ working tree trước khi thay đổi principal, chạy procedure file hai lần và Docker db-init lại, chứng minh quyền được cấp lại và password đã đổi được giữ nguyên. Account UI được triển khai trong Epic 1.6; đổi mật khẩu UI và tích hợp CRUD Sinh viên thuộc các milestone sau. Per-user Python connection được triển khai trong Epic 1.5.

## Epic 1.5 — Đăng nhập bằng SQL Server account

Login form mở connection `QLDSV` bằng chính username/password vừa nhập, chạy `EXEC dbo.sp_ThongTinDangNhap` trên cùng connection và chỉ nhận QLDSV_ADMIN → Admin, QLDSV_GIANGVIEN → GiangVien, QLDSV_SINHVIEN → SinhVien. `DatabaseUser` trả về là MAGV tin cậy của Admin/GiangVien hoặc MASV của Student; không lấy MASV/role từ UI hoặc `TaiKhoan`.

Ứng dụng chỉ cần `DB_DRIVER`, `DB_SERVER`, `DB_DATABASE` để xác định đích kết nối. Ví dụ Docker dùng `DB_SERVER=localhost,14330`; cấu hình local phải trỏ đúng instance. Không cần `DB_USERNAME`, `DB_PASSWORD` hoặc Trusted Connection. Các biến `QLDSV_ADMIN_*` chỉ phục vụ bootstrap/verifier, không thay credential của Login form.

Session sở hữu connection `QLDSV` đang đăng nhập; Admin có thêm connection `master` mở bằng cùng credential và được kiểm tra cùng SQL Login. GiangVien/Student không có connection master. Connection dài hạn dùng `autocommit=True`; ODBC pooling bị tắt trước khi connect. Repository mượn connection và chỉ đóng cursor. Password không nằm trong User/session, không được giữ lại để reconnect hoặc ghi log. Logout, đóng cửa sổ và shutdown giải phóng các SQL session; mất kết nối yêu cầu đăng nhập lại.

Backup/Restore repository mượn master của Admin. Trước khi restore, connection QLDSV được đóng; sau lần restore đã bắt đầu (thành công hoặc lỗi), session bị xóa và phải đăng nhập lại. Nếu master không thể thực hiện cleanup MULTI_USER, ứng dụng báo lỗi để xử lý SQL Server thủ công; không mở lại connection bằng password lưu sẵn. Mapping đường dẫn Windows/container và migration Backup/Restore đầy đủ vẫn thuộc milestone sau.

Epic 1.5 chỉ đổi cách repository mượn connection. Epic 1.6 tiếp tục migrate Account Management như mô tả bên dưới; riêng Change Password còn legacy, chờ Epic 1.7.

Kiểm chứng app layer bằng SQL principals thật (ODBC + `.venv`):

```powershell
.\.venv\Scripts\python.exe docker/verify-authentication.py
```

Verifier nhận password Admin hiện tại từ hidden prompt hoặc process `QLDSV_ADMIN_PASSWORD`, dùng target `DB_*` như app. Nó yêu cầu các seed identity `GV00000003` (Admin), `GV00000002` (GiangVien), `SV00000002` (Student) chưa có Login/User; tạo account qua security SP, kiểm tra SQL identity, repository, own-score SP và SQL denials. Nó giữ connection app để chứng minh DROP LOGIN bị chặn, logout rồi xóa thành công để chứng minh connection vật lý đã đóng. Principals tạm được dọn trong `finally`; không reset password demo, không sửa Student/score data và không restore QLDSV.

Unit/regression tests:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
```

## Epic 1.6 — Quản lý SQL Server account

Admin mở **Quản lý tài khoản** để xem/tạo/xóa SQL Login/User. Danh sách đọc `sys.server_principals`, `sys.sql_logins`, `sys.database_principals`, `sys.database_role_members`, chỉ lấy Login/User cùng tên, cùng SID và đúng một business role. Query tự kiểm tra SQL caller là Admin hợp lệ trước khi trả dữ liệu; Python authorization và ẩn menu không thay thế quyền SQL Server.

Có ba application role: QLDSV_ADMIN → Admin, QLDSV_GIANGVIEN → GiangVien, QLDSV_SINHVIEN → SinhVien. Admin/GiangVien bắt buộc MAGV có sẵn; Student bắt buộc MASV có sẵn. Họ tên staff lấy từ Giangvien, Student từ Sinhvien. Trạng thái phản ánh `sys.sql_logins.is_disabled`, không còn cột trạng thái ứng dụng.

- **Tạo Admin/GiangVien:** MAGV bắt buộc, không có Username/LoginName input. Password tùy chọn, trống gửi NULL để SQL áp Qldsv@123456, CHECK_POLICY=ON. Chỉ Admin có QLDSV_ACCOUNT_ADMIN + dbcreator.
- **Tạo SinhVien:** MASV bắt buộc, service derive Login/User theo MASV, không nhận mật khẩu ghi đè. Python gửi `@Password=NULL` cho `dbo.sp_TaoTaiKhoan`; SQL Server áp dụng mặc định `123456`, `CHECK_POLICY=OFF`. `AccountService.create_student_account(masv)` là API ổn định để Người 2 tích hợp sau.
- **Xóa:** xác nhận trước khi gọi `dbo.sp_XoaTaiKhoan`, thành công tải lại danh sách. SQL Server chặn self-delete, account sai mapping/role, ownership hoặc phiên SQL còn hoạt động; không KILL session. Account có phiên hoạt động cần đăng xuất trước khi xóa.

List/create/delete không sử dụng `dbo.TaiKhoan`. Repository chỉ mượn connection SQL đã xác thực; không tạo principal bằng SQL động từ Python, không reconnect hoặc dùng credential cố định. Lỗi `520xx` được chuyển thành thông báo an toàn. Mất kết nối vẫn invalidates session và đưa người dùng về Login.

Epic 1.6 không hỗ trợ Edit, đổi role/mapping hoặc Lock/Unlock. **Change Password vẫn chờ Epic 1.7**; legacy `update_password()` được giữ riêng, chưa hoạt động với SQL Login khi không có bảng legacy.

Kiểm chứng bằng real Admin principal trên database đã bootstrap, không có bảng legacy:

```powershell
.\.venv\Scripts\python.exe docker/verify-account-management.py
```

Verifier dùng target `DB_*`, nhận `QLDSV_ADMIN_LOGIN` (mặc định `GV00000001`) và password **hiện tại** từ process `QLDSV_ADMIN_PASSWORD` hoặc hidden prompt, không đọc secret bootstrap để đoán password. Nếu dùng prompt, hỏi lại khi đăng nhập Admin sau khi logout Student. `QLDSV_STUDENT_LOGIN` là demo Student có sẵn; `QLDSV_VERIFY_STUDENT` mặc định `SV00000002`, `QLDSV_VERIFY_ADMIN` mặc định `GV00000003`, `QLDSV_VERIFY_LECTURER` mặc định `GV00000002`; tất cả phải có business row nhưng chưa có Login/User. Script từ chối tái sử dụng principal có sẵn.

Verifier list/tạo qua `AccountService`; create trả nguyên SID output từ `sp_TaoTaiKhoan` qua repository/service. SID này là bằng chứng ownership, không lấy từ metadata sau khi tạo. Script kiểm tra technical memberships, chặn delete khi có session, tạo Student và login `MASV/123456` qua `AuthService`, kiểm tra SQL-side/service denials rồi logout.

Mọi thao tác dọn disposable principal (qua repository hoặc control connection trong `finally`) đều truyền `@ExpectedSid` đã nhận khi tạo. Các test self-delete, active-session và Student-denied vẫn dùng đường production thông thường để kiểm tra từ chối. Script còn cố xóa Admin disposable với SID sai, yêu cầu `52016` và kiểm tra Login/User/memberships còn nguyên trước khi xóa với SID đúng. Metadata precheck chỉ xử lý trường hợp đã vắng; SQL procedure quyết định identity cuối cùng, không retry xóa chỉ theo tên khi mismatch. Cleanup lỗi yêu cầu kiểm tra thủ công. Cần procedure contract mới từ `StoredProcedures_Security.sql` trước khi chạy verifier. Không dùng `sa`, không sửa business rows/điểm, không KILL hoặc Restore QLDSV.

Tests Epic 1.6 riêng:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_epic_1_6_accounts.py' -v
```

## Quản lý giảng viên (Admin)

Dashboard Admin có **Quản lý giảng viên** ngay sau Quản lý sinh viên. Module list/thêm/sửa/xóa `dbo.Giangvien` qua model/service/repository riêng, mượn SQL session đang đăng nhập. Bảng/form chỉ MAGV, Họ, Tên, Phái; MAGV không thể đổi khi sửa. GiangVien/SinhVien không có menu và bị chặn ở service lẫn SQL.

Thêm giảng viên chỉ thêm business entity, không tạo SQL credentials. Admin cấp Admin/GiangVien access sau đó bằng **Quản lý tài khoản**, dùng MAGV có sẵn. Xóa giảng viên bị chặn nếu còn SQL Login hoặc Database User: phải xóa account ở Quản lý tài khoản trước. PhanCong cũng chặn xóa; module không auto-delete account hoặc cascade assignment.

File mới `database/StoredProcedures_Lecturer.sql` giữ common listing `sp_GetGiangVien`, bổ sung `sp_ThemGiangVien`, `sp_CapNhatGiangVien`, `sp_XoaGiangVien`, cùng object-specific Admin grants/non-Admin denials. Delete khóa Giangvien `UPDLOCK,HOLDLOCK` trong transaction trước metadata/assignment checks, phối hợp với staff account creation để tránh orphan identity. SQL kiểm tra quyền metadata của Admin và FK PhanCong phải còn bật, trusted, không cascade.

Docker bootstrap đã đăng ký file mới sau Security.sql và StoredProcedures_Security.sql. **SQL deployment vẫn là bước riêng**; implementation source không deploy, không khởi động/reset Docker và không thay compatibility level. Cần triển khai source SQL đầy đủ trước khi dùng module trên DB thật.

Unit tests (không cần SQL live):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_lecturer_management.py' -v
```

Verifier chỉ được chạy **sau khi được phép deploy và `database/StoredProcedures_Lecturer.sql` đã được triển khai**, cần password Admin hiện tại:

```powershell
.\.venv\Scripts\python.exe docker/verify-lecturer-management.py
```

Verifier chưa chạy trong task source này. Nó fail closed khi thiếu prerequisites, chỉ dùng application Admin và disposable MAGV/account/PhanCong, giữ CreatedSid/ExpectedSid khi dọn account; không reset mật khẩu, KILL session hoặc restore DB. Kiểm chứng live SQL và concurrency còn chờ deployment/credential phù hợp. Epic 1.7 và grading vẫn deferred.

## Reset database development

Muốn xóa hoàn toàn Docker database và dựng lại từ script:

```powershell
docker compose down -v
docker compose up -d --build
```

`down -v` xóa named volume database. Không chạy lệnh này nếu container đang chứa dữ liệu cần giữ.

## Backup volume

Repository bind-mount:

```text
Host:      .\backups
SQL Server container: /var/opt/mssql/backups
```

Phần Backup/Restore của app hiện cần được điều chỉnh ở milestone tương ứng vì Python chạy trên Windows còn SQL Server chạy trong Linux container; hai phía nhìn cùng file qua hai path khác nhau.

## Cài Python application

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Chạy `.\.venv\Scripts\python.exe -m app.main`, nhập SQL Login và password hiện tại. Authentication và Account Management list/create/delete không phụ thuộc `dbo.TaiKhoan`; đổi mật khẩu còn chờ Epic 1.7.

## Cấu trúc chính

- `app/`: Python/PySide6 desktop application.
- `database/Database_QLDSV.sql`: Epic 1.1, schema cốt lõi.
- `database/CreatePhanCong.sql`: bảng bổ trợ phân công giảng dạy.
- `database/storedProcedure.sql`: Epic 1.2, SP-01 -> SP-09.
- `database/seedData.sql`: DB-09 test/demo data.
- `docker-compose.yml`: SQL Server + database bootstrap orchestration.
- `docker/db-init.Dockerfile`: image one-shot cho bootstrap scripts.
- `docker/init-db.sh`: thứ tự init và verification.
- `specs/`: đặc tả triển khai theo backlog revised.
- `AGENTS.md`: quy tắc cho coding agent trong repository.

Target SQL Server 2022 Developer Linux 16.0.4305.5 (`2022-latest`), compatibility_level hiện tại 160; không tự ALTER. Giữ security SP DROP/CREATE style và semantics đã kiểm thử.

## Triển khai milestone ba role trên DB hiện có

Thứ tự triển khai SQL bắt buộc:

1. `database/Security.sql` — dùng provisioning principal và luồng biến SQLCMD hex hiện có để thiết lập nền tảng ba role.
2. `database/StoredProcedures_Security.sql` — chỉ triển khai sau nền tảng ba role, bằng application Admin hiện tại hợp lệ.
3. `database/StoredProcedures_Lecturer.sql` — triển khai tiếp sau security procedures, bằng application Admin hiện tại hợp lệ.

Đây là hướng dẫn cho bước deployment riêng, không xác nhận Lecturer SQL đã được deploy. Không reset database, không đổi compatibility_level hoặc mật khẩu/policy của Login có sẵn. Không deploy riêng một phần migration.

Nếu thiếu `QLDSV_ADMIN_PASSWORD` hiện tại, deployment và real-principal tests còn blocked; không đoán, reset hoặc dùng sa thay Admin. Verifier noninteractive fail closed trước mọi mutation nếu thiếu credential này. Thứ tự kiểm chứng: `verify-security.py` → `verify-security-procedures.py` → `verify-authentication.py` → `verify-account-management.py` → `verify-lecturer-management.py`. Chỉ chạy `docker/verify-lecturer-management.py` sau khi `database/StoredProcedures_Lecturer.sql` đã được deploy.

Generic Admin thiếu MAGV, dual/triple membership và role name/type/owner/SID drift đều cần xử lý thủ công; bootstrap không tự sửa. Change Password vẫn deferred Epic 1.7; grading cuối cùng phải enforce PhanCong ở SQL SP như specs/06-grading.md.
