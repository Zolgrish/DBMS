# 02 - SQL Server Security & Authentication

**Owner chính:** Người 1  
**Tickets:** SEC-01..SEC-07, AUTH-01..AUTH-08

## Kiến trúc mục tiêu

```text
Form Login
   -> SQL Server Login (server scope)
   -> Database User trong QLDSV
   -> Database Role
      -> QLDSV_ADMIN
      -> QLDSV_GIANGVIEN
      -> QLDSV_SINHVIEN
   -> GRANT / DENY / EXECUTE
```

`dbo.TaiKhoan` không tham gia xác thực hoặc xác định role.

## SEC-01 - Authentication mode

Nếu dùng SQL Login, SQL Server instance phải hỗ trợ SQL Server Authentication (Mixed Mode). Đây là bước setup môi trường và phải được xác nhận trong SSMS.

## SEC-02 - Login vs User

- Login tồn tại ở server scope.
- User tồn tại trong database `QLDSV` và map tới Login.
- Login phải được tạo trước User.

## SEC-03 - Database roles

Tạo đúng 3 role nghiệp vụ:

- `QLDSV_ADMIN`
- `QLDSV_GIANGVIEN`
- `QLDSV_SINHVIEN`

Mỗi application User phải thuộc đúng một trong ba business role.

User phải có đúng một membership trực tiếp trong `sys.database_role_members`, trùng với business role đã xác định; không được thuộc thêm `db_owner` hoặc custom database role. Membership mặc định `public` không tạo row trực tiếp và không được đếm. Quy tắc được enforce ở cả drift preflight `Security.sql` và runtime `dbo.sp_ThongTinDangNhap`: role bổ sung xuất hiện sau bootstrap làm login bị từ chối với `52021`, không publish session. Login/User/SID và MAGV/MASV vẫn phải hợp lệ.

## SEC-04 - Admin permissions

Admin phải thực hiện được chức năng của đề, bao gồm CRUD nghiệp vụ, tạo/xóa account theo thiết kế và backup/restore.

Admin dùng QLDSV_ACCOUNT_ADMIN + dbcreator; không securityadmin/sysadmin.

## SEC-05 - Student permissions

`QLDSV_SINHVIEN`:

- không `INSERT/UPDATE/DELETE` bảng nghiệp vụ;
- không đọc trực tiếp toàn bộ điểm;
- chỉ được `EXECUTE` SP cần thiết để xem điểm của chính mình và chức năng student được phép;
- không có server role quản trị.

## SEC-06 - Permission matrix

Đây là **ma trận quyền chuẩn** của hệ thống. Ký hiệu `—` nghĩa là không có chức năng riêng/không áp dụng cho role đó; không được diễn giải thành một quyền mở rộng ngầm.

| Nghiệp vụ | Admin | GiangVien | SinhVien |
|---|---|---|---|
| Quản lý lớp | Allow | Deny | Deny |
| Xem lớp được phân công | Allow | Allow theo `PhanCong` | Deny |
| Xem lớp của mình | Allow | — | Allow |
| Quản lý sinh viên | Allow | Deny | Deny |
| Xem SV lớp đang dạy | Allow | Allow theo `PhanCong` | Deny |
| Xem hồ sơ bản thân | — | Allow | Allow |
| Quản lý giảng viên | Allow | Deny | Deny |
| Quản lý môn học | Allow | Deny | Deny |
| Xem môn được phân công | Allow | Allow theo `PhanCong` | Allow theo lớp của mình |
| Quản lý phân công | Allow | Deny | Deny |
| Xem phân công cá nhân | Allow | Allow của chính MAGV | Deny |
| Xem tất cả điểm | Allow | Deny | Deny |
| Xem điểm lớp/môn phụ trách | Allow | Allow theo `PhanCong` | Deny |
| Xem điểm bản thân | Allow | — | Allow |
| Nhập điểm | Allow | Allow theo `PhanCong` | Deny |
| Sửa điểm | Allow | Allow theo `PhanCong` | Deny |
| Xóa điểm | Allow | Deny | Deny |
| Quản lý tài khoản | Allow | Deny | Deny |
| Khóa/mở tài khoản | Allow | Deny | Deny |
| Đổi mật khẩu bản thân | Allow | Allow | Allow |
| Backup | Allow | Deny | Deny |
| Restore | Allow | Deny | Deny |

Các quyền có chữ `theo PhanCong` phải được SQL Server enforce từ `DatabaseUser = MAGV` tin cậy và `dbo.PhanCong(MAGV,MALOP,MAMH)`. Không cho UI truyền MAGV tùy ý để tự quyết định scope. SinhVien xem lớp/môn/điểm phải suy từ `DatabaseUser = MASV` và dữ liệu liên quan tới chính sinh viên đó. Object-level `GRANT/DENY/EXECUTE` có thể khác nhau theo thiết kế SP, nhưng hành vi quan sát phải đúng ma trận trên.

## SEC-07 - Test trực tiếp trong SSMS

Bắt buộc có account Admin, GiangVien và Student thật để chứng minh:

- Student login vào được.
- Student gọi SP xem điểm của mình được.
- Student `SELECT` trực tiếp dữ liệu điểm ngoài quyền -> bị từ chối.
- Student `INSERT/UPDATE/DELETE` -> bị từ chối.
- Admin thực hiện các quyền được cấp.
- GiangVien xem được lớp/SV/môn/phân công/điểm trong phạm vi `PhanCong`, nhập/sửa điểm trong phạm vi đó và bị từ chối khi vượt phạm vi.
- GiangVien bị từ chối xóa điểm, quản lý account và Backup/Restore.
- Cả ba role đổi mật khẩu bản thân được.

## AUTH-01..AUTH-08 - App login lifecycle

1. Form có LoginName/password.
2. App thử mở connection tới `QLDSV` bằng chính credential người dùng nhập.
3. Connection fail -> báo login thất bại; không fallback sang account DB dùng chung.
4. Connection success -> lấy database user + role membership từ SQL Server.
5. Chỉ chấp nhận UI role `Admin`, `GiangVien`, `SinhVien`.
6. Menu được điều chỉnh theo role nhưng DB vẫn là lớp bảo mật chính.
7. Repository/service sau login dùng connection/principal của phiên user hiện tại.
8. Logout đóng connection/session liên quan và xóa password khỏi state.

## Acceptance checklist

- Không có query login kiểu `SELECT ... FROM dbo.TaiKhoan WHERE username/password` trong flow mục tiêu.
- Có đủ ba business roles; Lecturer không có master/account/backup quyền.
- Quyền nghiệp vụ của cả ba role khớp ma trận SEC-06 và được enforce ở SQL Server, đặc biệt scope `PhanCong` của GiangVien.
- Student bị SQL Server chặn kể cả gọi repository/service trực tiếp.
- App không quay về fixed privileged DB credential sau khi login.


## Milestone ba role (yêu cầu mới)

- Mỗi application SQL User thuộc đúng một role owned by dbo: QLDSV_ADMIN -> Admin; QLDSV_GIANGVIEN -> GiangVien; QLDSV_SINHVIEN -> SinhVien.
- LoginName thuộc server scope và DatabaseUser/Username thuộc database scope; hai tên được phép khác nhau và được map 1:1 bằng SID. Mọi drift check/runtime auth phải xác minh SID, không dùng `LoginName = DatabaseUser` làm điều kiện an toàn. Same-name account cũ vẫn hợp lệ.
- DatabaseUser/Username phải là business identity có sẵn: Admin/GiangVien = Giangvien.MAGV, SinhVien = Sinhvien.MASV. Account Management nhận LoginName riêng và MAGV/MASV riêng; không suy MAGV/MASV từ LoginName.
- Staff password NULL/rỗng => SQL áp Qldsv@123456; custom/default đều CHECK_POLICY=ON. Student input password NULL/rỗng, SQL áp 123456, CHECK_POLICY=OFF. Bootstrap Admin vẫn yêu cầu QLDSV_ADMIN_PASSWORD riêng.
- Chỉ Admin có master connection, QLDSV_ACCOUNT_ADMIN + dbcreator, Account Management và Backup/Restore. GiangVien/SinhVien không server admin role/grants.
- GiangVien không có direct table CRUD rộng hoặc schema-wide EXECUTE. Chỉ GRANT các SP/query object-specific cần cho các quyền trong SEC-06; mọi thao tác xem lớp/SV/môn/phân công/điểm và nhập/sửa điểm phải giới hạn bằng MAGV hiện tại + `dbo.PhanCong(MAGV,MALOP,MAMH)`.
- SinhVien chỉ GRANT các SP/query object-specific để xem lớp của mình, hồ sơ bản thân, môn của lớp mình, điểm bản thân và đổi mật khẩu; không đọc trực tiếp toàn bộ bảng nghiệp vụ.
- Drift generic Admin thiếu MAGV, multi-role, sai role type/owner hoặc SID mapping: fail rõ, không tự repair/remap/xóa/reset password hoặc policy. Giữ @CreatedSid/@ExpectedSid và SID recheck trước DROP LOGIN; không KILL sessions.
- Đổi mật khẩu bản thân là quyền của cả ba role và phải tác động SQL Login hiện tại; không dùng `dbo.TaiKhoan`.
- Runtime đích SQL Server 2022 Developer Linux 16.0.4305.5, compatibility_level QLDSV hiện tại 160; không tự ALTER. Security SP giữ DROP/CREATE style và semantics transaction/rollback/SID đã kiểm thử.
