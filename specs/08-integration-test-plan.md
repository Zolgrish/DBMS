# 08 - Integration & Test Plan

**Tickets:** INT-01..INT-22

## Thứ tự triển khai

1. **Foundation:** schema + constraints + common SP.
2. **Security Foundation:** role, Admin Login/User, security SP, SSMS permission tests.
3. **App Authentication:** SQL credentials, DB-derived role, per-user connection.
4. **Parallel development:** CRUD/Nhập điểm, Report, Account/Password/Backup.
5. **Integration:** auto student account -> grading -> reports -> DB permissions -> backup/restore -> end-to-end.

## Integration matrix

| Ticket | Scenario | Expected |
|---|---|---|
| INT-01 | Merge DB + application | App chạy với schema/security target |
| INT-02 | CRUD dùng DB chung | CRUD đúng constraint và principal |
| INT-03 | Report dùng DB | Report đúng dữ liệu/quyền |
| INT-04 | Thêm SV | Tự tạo SQL Login mặc định `MASV`, DatabaseUser `MASV`, role Student |
| INT-05 | Admin login thật | Login được trong SSMS + app, quyền Admin đúng |
| INT-06 | Student login thật | Chỉ xem điểm chính mình |
| INT-07 | Student DML trực tiếp | `INSERT/UPDATE/DELETE` bị SQL Server từ chối |
| INT-08 | Connection sau login | Không dùng fixed privileged DB account |
| INT-09 | Lần thi 1 -> 2 | Đúng điều kiện `<5`/vắng và update |
| INT-10 | SV nghỉ học | Không xuất hiện trong nghiệp vụ chính |
| INT-11 | Report dữ liệu thật | Đúng query/MAX/xếp loại theo rule đã chốt |
| INT-12 | Backup -> đổi data -> Restore | Khôi phục được bằng Admin login |
| INT-13 | Đổi SQL password bản thân | Cả 3 role: cũ fail, mới success sau đổi |
| INT-14 | Exception | Không crash, lỗi có thông điệp phù hợp |
| INT-15 | UI/menu | Nhất quán với role nhưng không thay DB security |
| INT-16 | Demo setup | Có database demo + account demo cho các role cần kiểm thử |
| INT-17 | End-to-end | Flow chính hoàn chỉnh |
| INT-18 | LoginName khác DatabaseUser | Cùng SID vẫn đăng nhập, resolve đúng role và business identity |
| INT-19 | PhanCong integrity/delete guard | PK/FK đúng; chặn xóa GiangVien còn phân công |
| INT-20 | GiangVien theo PhanCong | Allow trong scope, deny ngoài scope; nhập/sửa được, xóa điểm bị chặn |
| INT-21 | Khóa/mở SQL account | Admin được phép; GiangVien/SinhVien bị từ chối |
| INT-22 | Ma trận quyền 3 role | Chứng minh bằng SQL principal thật và UI/menu tương ứng |

## Security tests bắt buộc

### Admin principal

- Login trong SSMS bằng Admin credential.
- Là member `QLDSV_ADMIN`; có technical role `QLDSV_ACCOUNT_ADMIN` + `dbcreator`, không thuộc `securityadmin`/`sysadmin`.
- CRUD nghiệp vụ theo scope được phép.
- Tạo/xóa account bằng flow thiết kế.
- Backup/Restore bằng chính credential này.

### Student principal

- Login bằng `MASV/123456` sau khi auto-create mặc định; case LoginName khác MASV vẫn resolve `USER_NAME()=MASV`.
- Xem được lớp của mình, hồ sơ bản thân và môn thuộc lớp mình qua SP/query object-specific suy từ principal hiện tại.
- `sp_SinhVien_XemDiem` trả đúng dữ liệu của mình.
- Không xem được điểm SV khác.
- `SELECT` trực tiếp dữ liệu bị hạn chế theo permission matrix.
- `INSERT/UPDATE/DELETE` bị từ chối.
- Không gọi được SP quản trị account/backup/restore.

### GiangVien principal

- Login resolve đúng `DatabaseUser = MAGV` dù LoginName có thể khác MAGV.
- Xem được lớp được phân công, SV lớp đang dạy, môn được phân công và phân công cá nhân.
- Xem được điểm lớp/môn phụ trách; nhập và sửa điểm khi `PhanCong(MAGV,MALOP,MAMH)` tồn tại.
- Cùng thao tác với lớp/môn không được phân công phải bị SQL Server từ chối hoặc trả ngoài scope = 0 row theo hợp đồng SP.
- Xóa điểm luôn bị từ chối.
- Quản lý account, khóa/mở account, Backup/Restore và server-admin operations bị từ chối.
- Đổi mật khẩu bản thân được.

## Regression tests khi migrate khỏi `dbo.TaiKhoan`

- Login không còn phụ thuộc `dbo.TaiKhoan`.
- Không còn code path xác định quyền từ `VAITRO` trong bảng ứng dụng.
- Có QLDSV_GIANGVIEN -> GiangVien, MAGV identity và `PhanCong`-scoped read/grading theo ma trận quyền hiện tại.
- Password change không update `MATKHAU` của bảng ứng dụng.
- Student account creation không insert bảng account.
- README/test fixtures cũ phải được cập nhật cùng milestone implementation tương ứng, không giữ tài liệu mâu thuẫn sau khi migration hoàn tất.
- Có regression cho cả `LoginName != DatabaseUser` và legacy `LoginName = DatabaseUser`; cả hai phải map đúng bằng SID.

## Checklist nghiệm thu Người 1

- [ ] Không còn yêu cầu `dbo.TaiKhoan` trong auth core.
- [ ] Có 3 role DB owned by dbo, principals gắn đúng MAGV/MASV và chỉ một business role.
- [ ] Có script GRANT/DENY/role membership chạy lại có kiểm soát.
- [ ] App login bằng SQL credential của user.
- [ ] Student auto account login được.
- [ ] Student xem đúng lớp/hồ sơ/môn/điểm của mình, không xem dữ liệu ngoài scope và không DML.
- [ ] Admin CRUD/account/backup/restore bằng Admin login.
- [ ] Cả ba role đổi mật khẩu bản thân bằng SQL Login hiện tại; password cũ fail, password mới success.
- [ ] Backup history + restore confirm + connection handling đúng.
- [ ] Xóa SV không để account mồ côi.
- [ ] Có script/demo SSMS chứng minh quyền, không chỉ UI.
- [ ] Có case `LoginName != DatabaseUser` nhưng cùng SID và vẫn resolve đúng MAGV/MASV + role.
- [ ] `PhanCong` có PK/FK đúng và chặn xóa GiangVien đang còn phân công.
- [ ] GiangVien allow trong `PhanCong`, deny ngoài `PhanCong`; nhập/sửa được nhưng xóa điểm/account/Backup/Restore bị chặn.
- [ ] Admin khóa/mở SQL Login được; GiangVien/SinhVien bị từ chối.
- [ ] Ma trận quyền 22 nghiệp vụ được test bằng SQL principal thật và UI/menu không vượt quyền DB.

## Test bổ sung cho ba role

- Admin/GiangVien đều MAGV-backed; Student MASV-backed; mỗi DatabaseUser/Username đúng một trong ba role dbo-owned. LoginName có thể khác User và phải map 1:1 bằng SID. Account Management chỉ cấp SQL access cho entity có sẵn, không INSERT business person.
- Lecturer login/identity đúng MAGV, không master/account/backup quyền hoặc server admin roles; chỉ các SP/query object-specific trong ma trận được phép. SQL phải enforce `PhanCong` cho xem lớp/SV/môn/phân công/điểm và nhập/sửa điểm; xóa điểm bị từ chối.
- Staff password NULL/rỗng dùng Qldsv@123456, CHECK_POLICY=ON; weak custom bị từ chối. Student giữ NULL input, 123456 và policy OFF. Thiếu MAGV => 52017; cross-identity fields bị Python từ chối.
- Test dual/triple roles, role type/owner collision, LoginName/User khác tên hợp lệ, missing/duplicate SID mapping, generic Admin thiếu MAGV, mapping/SID drift; create/delete/status phải fail closed khi một trong ba business role không còn là role non-fixed owned by `dbo`, không tự repair/reset password/policy.
- Giữ regression `CreatedSid`/`ExpectedSid`: successful create phải trả SID; delete/status luôn truyền SID đã capture và NULL/rỗng/stale SID phải bị `52016` trước mutation. Active-session/ownership/self-delete vẫn rollback, không KILL. Verifier dùng seed MAGV/MASV có thể cấu hình, preflight Login/User phải vắng; disposable business fixtures dọn trong finally, seed rows giữ nguyên. Live security verifier nên tạo owner drift tạm thời, xác nhận create/delete/status bị `52008`, target không đổi, rồi restore owner `dbo` trước cleanup SID-guarded.
- Change Password áp dụng cả ba role. Assignment-scoped grading là quyền mục tiêu hiện tại và phải enforce `PhanCong(MAGV,MALOP,MAMH)` trong SQL SP.
- Đích SQL Server 2022, compatibility hiện tại 160 giữ nguyên. Thiếu Admin password hiện tại => real-principal tests/deployment blocked; không dùng sa thay application principal.

## Lecturer CRUD và ranh giới account (GV-01..09 / INT-02, INT-05, INT-15, INT-19)

- Admin menu có Quản lý giảng viên ngay sau Quản lý sinh viên; GiangVien/SinhVien không có. List dùng common sp_GetGiangVien; mutations dùng lecturer SP riêng và current session, không mở shared connection.
- Thêm GV00000004 chỉ tạo Giangvien; không có Login/User/role mới. Sau đó Account Management có thể cấp Admin hoặc GiangVien SQL account cho MAGV này. Lecturer form không Username/Password/role controls.
- Edit khóa MAGV, chỉ HO/TEN/PHAI; vẫn sửa được khi account cùng MAGV tồn tại. Validate UTF-16 limits và nullable names ở Python/SQL.
- Xóa cần confirm; Database User = MAGV còn tồn tại hoặc có Login map cùng SID => 53006 và hướng dẫn Quản lý tài khoản. Sau xóa account với ExpectedSid gốc, lecturer còn PhanCong => 53007. Không cascade; xử lý đúng disposable assignment rồi xóa lecturer.
- Contract concurrency: delete khóa Giangvien UPDLOCK/HOLDLOCK trước metadata checks, giữ đến COMMIT. Account creation cùng giao thức khóa nên hai thứ tự cạnh tranh không để orphan Login/User. Live two-transaction proof còn phải chạy sau triển khai được phép; unit regex chỉ xác nhận source contract.
- Service từ chối Guest/Student/Lecturer; SQL object permissions và mutation guards từ chối principal thật. SessionRequiredError/driver errors được dịch an toàn, không lọt qua Qt.
- Bootstrap lecturer SP sau Security.sql và security SP; không sửa core schema, account SP, default passwords hoặc compatibility level.
- Unit command: `.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_lecturer_management.py' -v`.
- Future command sau deploy: `.\.venv\Scripts\python.exe docker/verify-lecturer-management.py`; cần current application Admin credential. Verifier giữ CreatedSid/ExpectedSid, chỉ mutate unique lecturer/account/assignment rồi dọn finally. Không chạy verifier/deploy/reset trong implementation task này; không dùng sa thay chứng minh quyền application.
