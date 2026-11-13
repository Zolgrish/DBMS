# AGENTS.md - QLDSV

Tài liệu này là hướng dẫn làm việc cho mọi coding agent trong repository `D:\\DBMS`.
Mục tiêu là triển khai đồ án **Quản Lý Điểm Sinh Viên (QLDSV)** đúng đề và đúng backlog đã điều chỉnh theo bài giảng SQL Server 2014.

## 1. Source of truth

Ưu tiên theo thứ tự:

1. Yêu cầu trực tiếp mới nhất của người dùng.
2. `specs/` trong repository này.
3. Backlog revised: `Backlog_QLDSV_revised_theo_baigiang.docx`.
4. Đề đồ án `De1-QLDSV` và bài giảng SQL Server 2014.
5. Code hiện tại chỉ là **trạng thái đang chuyển đổi**, không được dùng để phủ định spec mới.

Nếu code/README cũ còn nói `dbo.TaiKhoan`, hoặc dùng một DB account chung để xác thực thì coi đó là legacy cần migrate, không phải kiến trúc mục tiêu.

## 2. Quyết định kiến trúc bắt buộc

### Authentication và authorization

- **Không dùng `dbo.TaiKhoan` làm nguồn xác thực/phân quyền.**
- Chuỗi bảo mật mục tiêu: **Server Login -> Database User -> Database Role -> GRANT/DENY/EXECUTE**.
- Form Login nhận LoginName/password và dùng chính credential SQL Login đó để kết nối SQL Server tới `QLDSV`.
- Sau khi login thành công, role phải lấy từ SQL Server (`IS_ROLEMEMBER` hoặc SP tương đương), không lấy từ cột `VAITRO` của bảng ứng dụng.
- Có đúng 3 business role, mỗi SQL User chỉ thuộc một role:
  - `QLDSV_ADMIN` -> UI role `Admin`.
  - `QLDSV_GIANGVIEN` -> UI role `GiangVien`.
  - `QLDSV_SINHVIEN` -> UI role `SinhVien`.
- Admin/GiangVien là identities gắn Giangvien.MAGV; Student gắn Sinhvien.MASV. Account Management chỉ cấp SQL access cho entity có sẵn.
- Application SQL User chỉ có đúng một membership trực tiếp trong `sys.database_role_members`, và role đó phải là business role đã xác định; không có role bổ sung. Cả drift preflight của `Security.sql` và runtime `sp_ThongTinDangNhap` đều enforce; thêm role không liên quan sau bootstrap làm authentication từ chối với `52021`. `public` mặc định không phải membership trực tiếp được đếm.
- Ẩn/disable menu chỉ là UX. **SQL Server phải tự từ chối thao tác trái quyền kể cả khi service/repository bị gọi trực tiếp.**
- Sau login, các query nghiệp vụ phải chạy dưới SQL principal của user đang đăng nhập; không quay về một `DB_USERNAME/DB_PASSWORD` chung có toàn quyền.

### Database

- Schema cốt lõi của đề gồm: `Lop`, `Sinhvien`, `Giangvien`, `Monhoc`, `Diem`.
- Repository còn có bảng bổ trợ `PhanCong` (`database/CreatePhanCong.sql`) để map Giảng viên - Lớp - Môn. Đây không thay thế 5 bảng cốt lõi nhưng phải được giữ và Docker bootstrap phải tạo nó.
- Constraints phải được enforce tại SQL Server, không chỉ validate ở UI.
- Nghiệp vụ chính chỉ làm việc với sinh viên `NGHIHOC = 0`; màn hình quản trị danh sách có thể vẫn hiển thị sinh viên nghỉ học.
- Ưu tiên Stored Procedure cho truy vấn/nghiệp vụ đúng tinh thần đề và bài giảng.
- Target SQL Server 2022; không tự thay compatibility_level (hiện tại 160). Giữ security SP DROP/CREATE style.

### Tài khoản sinh viên

- Khi thêm sinh viên thành công: username/login = `MASV`, database user = `MASV`, password mặc định = `123456`, role = `QLDSV_SINHVIEN`.
- Tạo account nghĩa là tạo **SQL Login + Database User + role membership**, không `INSERT dbo.TaiKhoan`.
- Khi xóa sinh viên phải xử lý account liên quan để không để Login/User mồ côi; thực hiện theo spec tích hợp trước khi xóa dữ liệu sinh viên.

### Quản lý giảng viên và SQL account

- Quản lý giảng viên (chỉ Admin) sở hữu CRUD `dbo.Giangvien`; Quản lý tài khoản sở hữu SQL Login/User/role. Thêm giảng viên không tự tạo account; Admin cấp SQL access riêng cho MAGV đã tồn tại.
- MAGV unique, không được đổi sau khi tạo; chỉ cập nhật HO/TEN/PHAI, kể cả khi giảng viên đã có account.
- Xóa giảng viên phải khóa row `UPDLOCK,HOLDLOCK` trong transaction, cùng thứ tự khóa với `sp_TaoTaiKhoan`, rồi chặn nếu Login hoặc Database User cùng MAGV còn tồn tại. Xóa SQL account trong Quản lý tài khoản trước; không auto-delete account và không để orphan SQL identity.
- Xóa bị chặn khi còn `PhanCong`; không cascade-delete phân công. FK hiện có là bảo vệ cuối cùng. CRUD business ở `StoredProcedures_Lecturer.sql`, tách khỏi security procedures.

### Sinh viên xem điểm

- Sinh viên chỉ được xem điểm của chính mình.
- Không cho UI truyền một `MASV` tùy ý để SP xem điểm sinh viên khác.
- SP xem điểm phải suy ra identity từ SQL principal/database user hiện tại hoặc mapping server-side đáng tin cậy.
- Sinh viên không được `INSERT/UPDATE/DELETE` dữ liệu nghiệp vụ và không được đọc trực tiếp toàn bộ `Diem`.

### Backup/Restore

- Chỉ Admin được dùng chức năng Backup/Restore.
- Test bằng chính Admin login đã cấp quyền; không dùng `sa` để che lỗi phân quyền.
- Restore là thao tác phá hủy/trạng thái lớn: phải confirm, xử lý connection tới database, và test trên dữ liệu thử nghiệm.

## 3. Những điểm chưa được phép tự suy diễn

Các điểm sau phải giữ trạng thái mở cho tới khi nhóm/người dùng chốt:

- `DIEM = NULL` có chính thức đại diện cho **vắng thi** hay không. Code hiện tại có thể đang dùng quy ước này nhưng spec nghiệp vụ chỉ chốt khi được xác nhận.
- Điểm trung bình là trung bình cộng hay có trọng số theo tín chỉ.
- Cách transaction/rollback cụ thể khi vừa tạo/xóa SQL principal vừa thêm/xóa sinh viên, miễn kết quả cuối không để dữ liệu/account mồ côi.
- Admin dùng QLDSV_ACCOUNT_ADMIN + dbcreator; không securityadmin/sysadmin.

Nếu một task phụ thuộc vào một điểm mở, agent phải ghi rõ và không âm thầm chọn phương án mới.

## 4. Quy tắc sửa code

- Trước khi sửa, đọc `specs/README.md` và spec liên quan.
- Không sửa file ngoài phạm vi task.
- Không overwrite/revert thay đổi chưa commit của người dùng. Luôn xem `git status --short` trước khi patch.
- Không commit secrets, password thật, connection string cá nhân hoặc file `.env`.
- Không log password; không giữ password trong state lâu hơn cần thiết; logout phải giải phóng connection/session và xóa credential khỏi state ứng dụng.
- Không dùng UI authorization làm lớp bảo mật duy nhất.
- Không thêm bảng/role/entity ngoài đề chỉ để thuận tiện nếu chưa cập nhật spec.
- Không đổi tên field/table của đề nếu không có migration và lý do rõ ràng.
- Các thao tác ghi nhiều dòng như nhập điểm hàng loạt phải atomic theo spec; lỗi giữa chừng phải rollback.
- Dynamic SQL liên quan Login/User/Role phải kiểm soát input; role chỉ nhận allowlist đã định nghĩa trong spec security.

## 5. Cấu trúc trách nhiệm

- **Người 1:** database foundation, common SP, SQL Server Security, authentication, account/password, backup/restore, security test scripts.
- **Người 2:** CRUD Lớp/Sinh viên/Môn học/Giảng viên, nhập điểm, tích hợp auto SQL account khi thêm/xóa SV.
- **Người 3:** 5 nhóm report, logic MAX điểm, ĐTB/xếp loại, dynamic tổng kết.

Không di chuyển trách nhiệm giữa các phần nếu không có lý do tích hợp rõ ràng.

## 6. Definition of Done chung

Một thay đổi chỉ được coi là xong khi:

1. Đúng acceptance criteria trong spec/ticket tương ứng.
2. Không phá constraint/schema hoặc quyền của role khác.
3. Có test phù hợp ở tầng Python và/hoặc script SSMS.
4. Với security: chứng minh bằng SQL principal thật, không chỉ mock role Python.
5. Với Student: test cả happy path và thao tác bị từ chối.
6. Với Backup/Restore: không chạy restore phá dữ liệu thật ngoài môi trường test được phép.
7. `git diff` chỉ chứa thay đổi có chủ đích; không lẫn format/rewrite file không liên quan.

## 7. Tài liệu spec

Bắt đầu từ `specs/README.md`. Mỗi file spec ghi rõ phạm vi, ticket IDs, acceptance criteria, dependency và test bắt buộc.

## Milestone ba role (yêu cầu mới)

- Mỗi application SQL User thuộc đúng một role owned by dbo: QLDSV_ADMIN -> Admin; QLDSV_GIANGVIEN -> GiangVien; QLDSV_SINHVIEN -> SinhVien.
- LoginName (server Login) và DatabaseUser/Username (principal trong QLDSV) là hai định danh độc lập; mapping phải được xác minh bằng SID, không bằng equality tên. Legacy `LoginName = DatabaseUser` vẫn hợp lệ.
- DatabaseUser/Username là business identity: Admin/GiangVien = Giangvien.MAGV đã tồn tại (10 ký tự), SinhVien = Sinhvien.MASV đã tồn tại. Account Management chỉ cấp SQL access cho entity có sẵn, không INSERT Sinhvien/Giangvien.
- Account Management nhận LoginName riêng và MAGV/MASV riêng; không được suy business identity từ LoginName. Student integration có thể mặc định LoginName=MASV để tương thích, nhưng SQL/API phải hỗ trợ LoginName khác DatabaseUser.
- Staff password NULL/rỗng => SQL áp Qldsv@123456; custom/default đều CHECK_POLICY=ON. Student input password NULL/rỗng, SQL áp 123456, CHECK_POLICY=OFF. Bootstrap Admin vẫn yêu cầu QLDSV_ADMIN_PASSWORD riêng.
- Chỉ Admin có master connection, QLDSV_ACCOUNT_ADMIN + dbcreator, Account Management và Backup/Restore. GiangVien/SinhVien không server admin role/grants.
- Ma trận quyền chuẩn nằm ở `specs/02-security-authentication.md`. GiangVien được xem lớp được phân công, SV lớp đang dạy, hồ sơ bản thân, môn được phân công, phân công cá nhân và điểm lớp/môn phụ trách; được nhập/sửa điểm theo `PhanCong`. GiangVien không quản lý danh mục/account, không xóa điểm, không Backup/Restore và không có server admin role/master connection.
- Các quyền GiangVien theo lớp/môn phải dùng SP/query object-specific suy MAGV từ DatabaseUser tin cậy (đã map SID với Login) và kiểm tra `dbo.PhanCong(MAGV,MALOP,MAMH)`. Không nhận MAGV tùy ý từ UI, không schema-wide EXECUTE và không dựa vào UI để enforce quyền.
- Drift generic Admin thiếu MAGV, multi-role, sai role type/owner hoặc SID mapping: fail rõ, không tự repair/remap/xóa/reset password hoặc policy. Giữ @CreatedSid/@ExpectedSid và SID recheck trước DROP LOGIN; không KILL sessions.
- Admin/GiangVien/SinhVien đều được đổi mật khẩu bản thân bằng SQL Login hiện tại; không dùng `dbo.TaiKhoan`. Chỉ Admin được quản lý và khóa/mở account.
- Runtime đích SQL Server 2022 Developer Linux 16.0.4305.5, compatibility_level QLDSV hiện tại 160; không tự ALTER. Security SP giữ DROP/CREATE style và semantics transaction/rollback/SID đã kiểm thử.
