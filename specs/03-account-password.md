# 03 - Account Management & Password

**Owner chính:** Người 1  
**Tickets:** SECSP-01..SECSP-06, ADM-01..ADM-07, PASS-01..PASS-05

## Account source

Account được quản lý bằng SQL Server principals/role membership, không bằng `dbo.TaiKhoan`.

Danh sách account phải dựa trên metadata SQL Server như server/database principals và role membership; implementation cụ thể có thể bọc bằng Stored Procedure.

## Security Stored Procedures

### SECSP-01 - `sp_TaoTaiKhoan`

Phải:

- kiểm tra Login/User trùng;
- tạo SQL Login;
- tạo Database User mapped với Login;
- add member vào role hợp lệ;
- chỉ nhận role allowlist `QLDSV_ADMIN`, `QLDSV_GIANGVIEN`, `QLDSV_SINHVIEN`;
- `LoginName` và `DatabaseUser` là input riêng; User phải được tạo `FOR LOGIN` và mapping xác minh bằng SID.
- `@DatabaseUser` là optional ở cuối signature để giữ compatibility caller cũ; NULL nghĩa là dùng LoginName làm DatabaseUser.
- Student: `DatabaseUser = MASV`; LoginName có thể khác MASV. Flow auto-create được phép mặc định LoginName=MASV để tương thích; password mặc định `123456`.

Không ghép trực tiếp tên principal/role từ input không kiểm soát.

### SECSP-02 - `sp_XoaTaiKhoan`

- Xử lý Database User và Login đúng thứ tự.
- Không cho xóa account của phiên hiện tại nếu việc đó làm hỏng session.
- Báo lỗi rõ khi principal không tồn tại hoặc đang bị sử dụng.

### SECSP-03 - `sp_ThongTinDangNhap`

Trả đủ thông tin để app nhận diện:

- LoginName;
- DatabaseUser;
- role membership (`QLDSV_ADMIN`, `QLDSV_GIANGVIEN`, `QLDSV_SINHVIEN`).

Admin/GiangVien bắt buộc DatabaseUser = MAGV có sẵn; SinhVien = MASV có sẵn.

User phải resolve đúng một business role và chỉ có đúng một membership trực tiếp trong `sys.database_role_members`, khớp role đó. Không role, nhiều business role hoặc thêm database role không liên quan đều bị `52021`; membership `public` mặc định không được đếm. `Security.sql` kiểm tra drift khi bootstrap và `sp_ThongTinDangNhap` kiểm tra lại mỗi lần runtime authentication, nên role thêm sau bootstrap cũng bị từ chối. Output vẫn ba cột `sysname`: `LoginName`, `DatabaseUser`, `RoleName`.

`StoredProcedures_Security.sql` target SQL Server 2022 / compatibility level 160, giữ DROP/CREATE style đã kiểm thử; không tự ALTER compatibility_level.

### SECSP-04 - `sp_SinhVien_XemDiem`

- Chỉ trả điểm của sinh viên đang đăng nhập.
- Không nhận `MASV` tùy ý từ UI làm nguồn quyết định quyền.
- Kết quả điểm phục vụ màn hình student và tuân theo rule MAX lần thi nếu màn hình yêu cầu điểm môn cuối cùng.

### SECSP-05 - Password mặc định

Account SV phải tạo được với password `123456` đúng đề. Nếu password policy môi trường chặn, cấu hình cho môi trường đồ án phải được ghi rõ và test được; không âm thầm đổi password mặc định.

### SECSP-06 - Input hardening

- role chỉ nhận allowlist;
- principal name được validate/quote an toàn;
- lỗi duplicate/invalid principal phải trở thành lỗi nghiệp vụ dễ hiểu cho app.

## ADM-01..ADM-07 - UI/service quản lý account

- Không tạo bảng `TaiKhoan`.
- Admin cấp Admin hoặc GiangVien account cho MAGV đã tồn tại; LoginName là credential name riêng, DatabaseUser/Username vẫn là MAGV.
- Tạo Student account được kích hoạt từ flow thêm SV của Người 2.
- Không cho trùng LoginName hoặc mapping lặp một MASV/MAGV.
- Danh sách account đọc từ SQL Server principals/role membership.
- Xóa account có confirm.
- Trạng thái từ `sys.sql_logins.is_disabled`.
- Chỉ Admin được khóa/mở account SQL Login; GiangVien/SinhVien không có chức năng này. Khóa/mở không được đổi DatabaseUser, SID mapping hoặc business role.

## PASS-01..PASS-05 - Đổi password bản thân

- User đổi password của chính SQL Login, không update bảng ứng dụng.
- Form có mật khẩu cũ, mật khẩu mới, xác nhận.
- Mật khẩu mới/xác nhận phải khớp.
- Sau đổi: password cũ login fail, password mới login success.
- Nếu làm màn hình quản trị theo hình đề cho giảng viên, chỉ hiển thị giảng viên đã có SQL account.

## Acceptance checklist

- Tạo SV account -> thấy Login ở server và User trong `QLDSV`.
- User thuộc đúng role.
- Duplicate bị chặn rõ ràng.
- Xóa account không để User/Login mồ côi theo flow đã chọn.
- Đổi password tác động SQL Login thật và áp dụng cho cả Admin/GiangVien/SinhVien.

## Hợp đồng cấp account ba role

- Account Management chỉ cấp SQL access cho entity đã tồn tại, không INSERT Sinhvien/Giangvien. UI/API nhận `LoginName` riêng và business identity riêng; DatabaseUser/Username derive từ MASV/MAGV, không derive từ LoginName.
- Admin/GiangVien: MAGV bắt buộc đúng 10 ký tự, SQL kiểm tra Giangvien với UPDLOCK/HOLDLOCK trong transaction. Password NULL/rỗng => Qldsv@123456; custom/default CHECK_POLICY=ON. Lỗi MAGV 52017, policy 52009. Bootstrap Admin vẫn yêu cầu QLDSV_ADMIN_PASSWORD riêng.
- Student: MASV có sẵn là DatabaseUser/Username; LoginName độc lập, input password NULL/rỗng, SQL áp 123456, CHECK_POLICY=OFF; lỗi MASV 52007. Cấm cross-identity fields và Student custom password.
- Caller Admin=1, GiangVien=0, SinhVien=0; mỗi User đúng một business role. Chỉ Admin nhận QLDSV_ACCOUNT_ADMIN + dbcreator; Lecturer/Student không có server admin roles.
- Giữ @CreatedSid/@ExpectedSid, SID recheck trước DROP LOGIN, self-delete/ownership/active-session rollback; không KILL. Drift không tự remap/repair/reset password/policy.
- Table: Username/Mã | Login name | Họ và tên | Vai trò | Trạng thái. Staff names từ Giangvien, Student từ Sinhvien. Admin có thao tác Thêm/Xóa/Khóa/Mở khóa/Đóng theo quyền mục tiêu; không tự ý đổi mapping hoặc role qua thao tác khóa/mở.
- Change Password là self-service cho cả ba role, dùng SQL Login hiện tại; không update bảng ứng dụng.
