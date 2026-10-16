# QLDSV desktop application

Ứng dụng desktop Python/PySide6 cho đồ án Quản lý điểm sinh viên. Database development được đóng gói bằng Docker để mọi thành viên clone repository và dựng lại cùng một SQL Server + schema + Stored Procedure + seed data.

## Trạng thái kiến trúc

- Epic 1.1: 5 bảng cốt lõi `Lop`, `Sinhvien`, `Giangvien`, `Monhoc`, `Diem`.
- Repository có thêm bảng bổ trợ `PhanCong` để map `Giangvien - Lop - Monhoc`.
- Epic 1.2: common Stored Procedure `SP-01 -> SP-09`.
- `dbo.TaiKhoan` đã bị loại khỏi kiến trúc mục tiêu. Docker **không** chạy `CreateTaiKhoan.sql` hoặc `seedTaiKhoan.sql`.
- Epic 1.3 đã bootstrap SQL Server Login -> Database User -> `QLDSV_ADMIN` / `QLDSV_SINHVIEN` -> GRANT/DENY. Security SP và app login thuộc Epic 1.4/1.5.
- Python authentication hiện vẫn đang trong giai đoạn migration khỏi code legacy `dbo.TaiKhoan`; không coi code auth cũ là source of truth.

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
6. StoredProcedures_Security.sql   (tự chạy khi file được thêm ở Epic 1.4)
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

`Security.sql` kiểm tra SQL Authentication/Mixed Mode rồi tạo Login trước User, xác minh SID, tạo đúng hai business role và cấp quyền tại SQL Server. Script tương thích SQL Server 2014; không tạo `dbo.TaiKhoan` hoặc role `QLDSV_GIANGVIEN`. Nếu principal có type/SID/mapping, ownership hoặc membership xung đột, bootstrap báo lỗi và rollback thay vì tự remap, đổi owner hoặc nâng quyền Student.

Biến môi trường **chỉ dùng lúc init**, được truyền cho service `db-init`:

| Biến | Giá trị mặc định / yêu cầu |
|---|---|
| `QLDSV_ADMIN_LOGIN` | `GV00000001` |
| `QLDSV_ADMIN_PASSWORD` | Bắt buộc khi tạo Admin Login lần đầu; dùng password mạnh, policy ON. Giá trị trong `.env.example` chỉ là placeholder. Có thể bỏ trống khi Login đã tồn tại. |
| `QLDSV_STUDENT_LOGIN` | `SV00000001`; phải trùng `Sinhvien.MASV` có sẵn sau seed |

Docker Compose cũng nhận các biến này từ môi trường process. Bootstrap mã hóa input thành UTF-16LE hex trước khi SQLCMD substitution để tránh SQL injection từ tên/password; hex vẫn là dữ liệu nhạy cảm, không bật echo input (`sqlcmd -e`) hoặc shell tracing. Password không được truyền trong command arguments hoặc in ra log.

Login có sẵn **không bị tạo lại, reset password hoặc đổi password policy**, kể cả khi chạy lại `docker compose up -d --build` với giá trị init khác. Student mới có password `123456`, `CHECK_POLICY=OFF` theo đề; cấu hình này chỉ áp dụng khi tạo Student demo, không áp dụng cho Admin. Các User phải thuộc đúng business role; không tự cho một User vào cả hai role.

| Quyền | Admin | Student |
|---|---|---|
| Kết nối `QLDSV` | GRANT CONNECT | GRANT CONNECT |
| Database | GRANT CONTROL ON DATABASE::QLDSV | DENY SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo |
| SP-01..SP-09 | Được thực thi qua CONTROL | DENY EXECUTE từng procedure |
| Server | GRANT ALTER ANY LOGIN; member `dbcreator` | Không server role quản trị hoặc quyền quản trị Login |
| Safe Student SP | Chờ Epic 1.4 | Chờ grant EXECUTE từng SP ở Epic 1.4 |

`ALTER ANY LOGIN` đủ cho tạo/đổi/xóa Login; `dbcreator` phục vụ Restore. Không cấp `sysadmin`, `securityadmin` hoặc nest custom role vào `db_owner`. Student không được GRANT/DENY EXECUTE toàn schema `dbo`; safe SP dùng static SQL cùng owner vẫn có thể hoạt động qua ownership chaining sau khi được grant riêng ở Epic 1.4.

Kết nối SSMS bằng **SQL Server Authentication**, server `localhost,14330`, database `QLDSV`:

- Admin: Login `GV00000001` (hoặc biến cấu hình), password đã cung cấp khi tạo Login lần đầu hoặc password hiện tại sau khi đổi.
- Student: Login `SV00000001` (hoặc MASV cấu hình), password ban đầu `123456`; sau khi đổi phải dùng password hiện tại.

Trong SSMS, xem **Security → Logins** ở server và **Databases → QLDSV → Security → Users / Roles → Database Roles**. Kết nối bằng Admin để kiểm tra metadata; dùng chính từng Login để chứng minh quyền:

```sql
USE QLDSV;
SELECT SUSER_SNAME() AS LoginName, USER_NAME() AS DatabaseUser,
       IS_ROLEMEMBER(N'QLDSV_ADMIN') AS IsAdmin,
       IS_ROLEMEMBER(N'QLDSV_SINHVIEN') AS IsStudent;
SELECT sp.name AS LoginName, dp.name AS DatabaseUser, r.name AS RoleName
FROM sys.server_principals sp
JOIN sys.database_principals dp ON dp.sid = sp.sid
JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
WHERE r.name IN (N'QLDSV_ADMIN', N'QLDSV_SINHVIEN');
```

Chạy kiểm chứng SEC-07 bằng SQL principals thật trên Docker stack đang chạy (Python standard library + Docker CLI):

```powershell
python docker/verify-security.py
```

Script hỏi kín password Admin hiện tại, hoặc nhận `QLDSV_ADMIN_PASSWORD` từ process. Nếu đã đổi tên Login/password Student, đặt thêm `QLDSV_ADMIN_LOGIN`, `QLDSV_STUDENT_LOGIN`, `QLDSV_STUDENT_PASSWORD` tương ứng. Script không đọc/ghi `.env`. SA chỉ kiểm tra metadata và chạy bootstrap; mọi test quyền Admin đều kết nối bằng Admin Login.

Test gồm identity/role, Student data/SP denials, Admin CRUD/DDL/Login management, Backup/Restore trên **database tạm có tên duy nhất**, và hai lần bootstrap lại. Test tạm đổi password Student để chứng minh bootstrap không reset, rồi phục hồi password ban đầu trong `finally`; nên chạy khi demo Student không có phiên làm việc cần giữ. Object/Login/database/file backup tạm được dọn sau test; không Restore hoặc thay đổi business data của `QLDSV`.

SEC-07 **chưa** nghiệm thu Student gọi `sp_SinhVien_XemDiem` thành công: SP này thuộc Epic 1.4. Login form dùng credential SQL người dùng thuộc Epic 1.5. Epic 1.3 không tạo SP giả hoặc sửa Python authentication để đánh dấu hai phần này hoàn tất.

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

Sau khi Epic 1.5 migration hoàn tất, Login form sẽ dùng username/password người dùng nhập để mở SQL connection tới `QLDSV`. Hiện tại code Python cũ vẫn còn tham chiếu `dbo.TaiKhoan`, vì vậy xóa bảng `TaiKhoan` trước khi migrate auth sẽ làm flow login cũ không hoạt động — đây là trạng thái chuyển tiếp đã biết.

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

SQL Server container hiện dùng image `2022-latest` cho môi trường phát triển reproducible; SQL scripts của đồ án vẫn phải giữ cú pháp tương thích SQL Server 2014 theo yêu cầu môn học.
