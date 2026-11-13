# 00 - Project Scope

## Mục tiêu

Xây dựng ứng dụng desktop quản lý điểm sinh viên bằng Python/PySide6 + SQL Server, đáp ứng đề QLDSV và thể hiện đúng các nội dung SQL Server Security đã học.

## Schema nghiệp vụ bắt buộc

Chỉ có 5 bảng cốt lõi do đề chỉ định:

- `Lop`
- `Sinhvien`
- `Giangvien`
- `Monhoc`
- `Diem`

`dbo.TaiKhoan` không thuộc kiến trúc mục tiêu cho authentication/authorization.

Repository có thêm bảng bổ trợ `dbo.PhanCong` từ `database/CreatePhanCong.sql` để biểu diễn phân công `MAGV + MALOP + MAMH`. Bảng này là extension phục vụ nghiệp vụ/tích hợp, không làm thay đổi việc đề quy định 5 bảng cốt lõi ở trên.

## Role nghiệp vụ

### Admin

- Được quản lý lớp, sinh viên, giảng viên, môn học, phân công, điểm và tài khoản theo ma trận quyền chuẩn.
- Được xem dữ liệu lớp/môn/phân công/điểm phục vụ quản trị; được nhập, sửa và xóa điểm.
- Có thể tạo/xóa SQL account theo quyền được cấp.
- Có thể khóa/mở SQL account theo chức năng quản trị tài khoản.
- Có thể đổi mật khẩu của chính SQL Login.
- Có thể backup/restore khi permission SQL Server cho phép.

### GiangVien

- Được xem lớp được phân công, sinh viên của lớp đang dạy, môn được phân công và phân công cá nhân.
- Được xem điểm của lớp/môn phụ trách; được nhập và sửa điểm **chỉ khi** `dbo.PhanCong(MAGV,MALOP,MAMH)` xác nhận đúng phạm vi.
- Được xem hồ sơ bản thân và đổi mật khẩu của chính SQL Login.
- Không quản lý lớp/sinh viên/giảng viên/môn/phân công/tài khoản; không xóa điểm; không backup/restore.

### SinhVien

- Được xem lớp của mình, hồ sơ bản thân, môn được phân cho lớp của mình và điểm của chính mình.
- Được đổi mật khẩu của chính SQL Login.
- Không được CRUD dữ liệu nghiệp vụ.
- Không được xem điểm sinh viên khác.
- Không được backup/restore.

## Quy tắc toàn cục

- App phải đăng nhập trước khi sử dụng.
- Security thật nằm ở SQL Server, không chỉ ở menu/UI.
- Nghiệp vụ chính bỏ qua sinh viên có `NGHIHOC = 1`.
- Query/SP mới target SQL Server 2022; không tự đổi compatibility_level.
- Ưu tiên Stored Procedure cho logic truy vấn/nghiệp vụ.

## Chia trách nhiệm

- Người 1: DB foundation + Security/Auth + Account/Password + Backup/Restore.
- Người 2: CRUD + Sinh viên + Nhập điểm + auto account integration.
- Người 3: Reports + tổng hợp điểm.

## Open decisions

1. **Vắng thi:** đề có khái niệm vắng nhưng `DIEM` là số. Nếu nhóm chốt `NULL = vắng`, phải áp dụng thống nhất ở schema, nhập điểm và report.
2. **ĐTB:** đề chưa nói trung bình cộng hay trọng số tín chỉ. Không tự chọn.
3. **Server permissions Admin:** QLDSV_ACCOUNT_ADMIN + dbcreator; không securityadmin/sysadmin.
4. **Xóa SV + account:** phải không để orphan SQL Login/User; cách transaction/compensation cụ thể cần được thiết kế khi triển khai.

## GiangVien và identity account

Ba business roles duy nhất: QLDSV_ADMIN -> Admin, QLDSV_GIANGVIEN -> GiangVien, QLDSV_SINHVIEN -> SinhVien; mỗi SQL User đúng một role. DatabaseUser/Username của Admin/GiangVien dùng MAGV có sẵn, Student dùng MASV có sẵn. Server LoginName là credential riêng, có thể khác DatabaseUser và phải map 1:1 bằng SID. Account Management chỉ cấp SQL access, không thêm business person.

Chỉ Admin có master connection, QLDSV_ACCOUNT_ADMIN + dbcreator và quyền quản trị account/backup. GiangVien không có server admin role/master connection; quyền đọc nghiệp vụ và nhập/sửa điểm phải đi qua SP/query được giới hạn theo `PhanCong`, với MAGV suy từ SQL principal tin cậy. SinhVien chỉ đọc dữ liệu cá nhân/lớp-môn của mình theo SP an toàn. Ma trận quyền đầy đủ tại `02-security-authentication.md`.
