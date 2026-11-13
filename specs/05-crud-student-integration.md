# 05 - CRUD & Student Account Integration

**Owner chính:** Người 2  
**Phối hợp Security:** Người 1  
**Tickets:** LOP-01..08, SV-01..14, MH-01..09, GV-01..08

## Quản lý Lớp

- Hiển thị danh sách lớp.
- Thêm/Xóa/Ghi/Phục hồi.
- `MALOP`, `TENLOP` không rỗng/trùng.
- Không xóa lớp khi FK sinh viên làm thao tác không hợp lệ.

## Quản lý Sinh viên

- Chọn lớp -> grid chỉ hiện SV của lớp đó.
- Thêm/Xóa/Ghi/Phục hồi/Tìm kiếm theo MASV/Họ tên.
- `PHAI`: `1 = Nam`, `0 = Nữ`.
- Validate ngày sinh.
- Hỗ trợ đường dẫn ảnh theo đề.
- CRUD quản lý danh sách có thể thấy sinh viên nghỉ học; nghiệp vụ chính bỏ `NGHIHOC = 1`.

### SV-12 - Auto SQL account

Sau khi thêm sinh viên thành công, tích hợp module Người 1 để tạo:

```text
LoginName    = MASV (mặc định tương thích; có thể khác khi cấp account riêng)
DatabaseUser = MASV
Password     = 123456
Role         = QLDSV_SINHVIEN
```

Đây là SQL Login + Database User + role membership, không phải `INSERT dbo.TaiKhoan`.

Nếu tạo account thất bại, flow phải không để hệ thống ở trạng thái khó hiểu. Cách rollback/compensation cụ thể là open design nhưng kết quả cuối phải nhất quán và có lỗi rõ cho user.

### SV-14 - Xóa SV và account

Không để orphan SQL Login/User. Backlog ưu tiên xử lý account trước khi xóa SV hoặc chặn xóa khi account chưa được xử lý.

## Quản lý Môn học

- CRUD + Thoát.
- `MAMH` unique.
- `TENMH` unique.
- `SoTCLT`, `SoTCTH >= 0`.

## Quyền xem dữ liệu danh mục theo role

- Admin có quyền quản lý lớp, sinh viên, giảng viên, môn học và phân công.
- GiangVien không CRUD các danh mục trên, nhưng được xem lớp được phân công, sinh viên của lớp đang dạy, môn được phân công, hồ sơ bản thân và phân công cá nhân. Mọi danh sách theo lớp/môn phải scope bằng `DatabaseUser = MAGV` + `dbo.PhanCong`.
- SinhVien không CRUD danh mục; được xem lớp của mình, hồ sơ bản thân và môn được phân cho lớp của mình. Scope phải suy từ `DatabaseUser = MASV`, không nhận MASV tùy ý từ UI để quyết định quyền.

## Quản lý Giảng viên

- **GV-01..08:** chỉ Admin được list/thêm/sửa/xóa business entity `dbo.Giangvien` qua Quản lý giảng viên. Model Lecturer tách khỏi User; service/repository mượn authenticated QLDSV session.
- `MAGV NCHAR(10)` unique, đúng 10 đơn vị UTF-16 và không khoảng trắng bao quanh; immutable sau tạo. HO/TEN nullable, tối đa 40/10 đơn vị UTF-16; PHAI bit (1 Nam, 0 Nữ). Sửa chỉ HO/TEN/PHAI; giảng viên đã có account vẫn sửa được các field này.
- Thêm chỉ INSERT Giangvien, không tạo SQL Login/User/role, không gọi AccountService/security account SP. Admin mở Quản lý tài khoản riêng để cấp Admin/GiangVien access cho MAGV đã có. Vì LoginName có thể khác MAGV, collision liên quan account phải dựa trên DatabaseUser/SID mapping chứ không suy từ tên Login.
- Xóa phải xóa SQL account trước trong Quản lý tài khoản; chặn nếu Database User MAGV còn tồn tại hoặc có Login map SID tới User đó (53006). Không auto-delete account, không để orphan identity.
- Chặn xóa nếu có PhanCong (53007); không cascade hoặc xóa assignment trong lecturer CRUD. Giữ FK làm bảo vệ cuối cùng.
- `StoredProcedures_Lecturer.sql`: dùng common `sp_GetGiangVien` và thêm `sp_ThemGiangVien`, `sp_CapNhatGiangVien`, `sp_XoaGiangVien`. Mỗi mutation tự kiểm tra mapped Admin, static SQL, TRY/CATCH/XACT_ABORT/transaction; lỗi an toàn 53001..53009. Cấp EXECUTE từng object cho Admin, DENY GiangVien/SinhVien.
- Xóa lấy `UPDLOCK,HOLDLOCK` trên row Giangvien **trước** kiểm tra principals/assignments. Khóa tương thích giao thức tạo staff account hiện có: tạo account lấy lock trước thì delete chờ và thấy account; delete commit trước thì account creation không thấy MAGV và fail. Kiểm tra PhanCong trong transaction với khóa và FK.
- UI: MAGV/Họ/Tên/Phái, Thêm/Sửa/Xóa/Đóng, không inline edit/account/password/role controls. MAGV edit read-only; xóa cần chọn row và confirm mã + họ tên. Reload sau mutation thành công; lỗi session dịch an toàn.

Acceptance: unit/UI/SQL contract trong `tests/test_lecturer_management.py`; future real Admin verifier `docker/verify-lecturer-management.py` kiểm tra CRUD, account/SID boundary, Lecturer SQL denials và PhanCong. Không chạy verifier hoặc deploy SQL trong task triển khai source này; live authorization/concurrency proof còn chờ bước triển khai được cho phép.

## Acceptance checklist tích hợp

- Thêm SV -> có SQL Login/User/role đúng.
- Student auto-created mặc định login bằng `MASV/123456` được; account cấp riêng với LoginName khác MASV cũng phải login và resolve về MASV đúng.
- Xóa SV không để principal mồ côi.
- Không có dependency vào `dbo.TaiKhoan`.

## Ranh giới tích hợp ba role

Account Management không tạo business person; nó chỉ cấp Login/User cho MASV/MAGV có sẵn. DatabaseUser/Username luôn là MASV/MAGV; LoginName là credential riêng map bằng SID. CRUD Sinhvien tạo entity trước khi gọi create_student_account(masv); wrapper mặc định LoginName=MASV, SQL áp 123456, CHECK_POLICY=OFF. Admin/GiangVien cùng gắn MAGV và CHECK_POLICY=ON, mỗi User đúng một role.

Chỉ Admin quản lý account/CRUD danh mục/backup. GiangVien không có server admin roles/master/direct CRUD rộng; các quyền đọc và grading chỉ qua SP/query object-specific kiểm tra `PhanCong` theo MAGV từ SQL principal và MALOP/MAMH. Cả ba role được đổi mật khẩu bản thân.
