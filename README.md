# QLDSV desktop application

Ứng dụng Python/PySide6 cho hệ thống quản lý điểm sinh viên. AUTH-01 đến AUTH-06 cung cấp đăng nhập, tạo session, điều hướng theo vai trò và đăng xuất. Các mục quản lý sinh viên, môn học, nhập điểm và xem điểm vẫn là menu khung.

## Epic 1.4 và đổi mật khẩu

- **ADM-02 Create account:** Admin xem danh sách, tạo và sửa tài khoản với vai trò và MASV/MAGV tương ứng.
- **ADM-03 Auto-create student account:** `AccountService.create_student_account(masv)` tạo username bằng MASV và mật khẩu `123456` sau khi xác nhận sinh viên tồn tại. Module Sinh viên sẽ gọi hàm này khi được triển khai.
- **ADM-04 Duplicate username validation:** username trùng bị từ chối trước khi thêm.
- **ADM-05 Admin has full permission:** Admin truy cập màn hình và các thao tác quản lý tài khoản.
- **ADM-06 Student can only view their own score:** menu Sinh viên chỉ có Xem điểm và Đổi mật khẩu. Mục Xem điểm hiện là placeholder; MASV được lấy từ session, không có đầu vào chọn sinh viên khác.
- **ADM-07 Unauthorized operations are blocked:** service kiểm tra quyền Admin trước khi đọc, tạo, sửa hoặc thay đổi trạng thái tài khoản, kể cả khi bị gọi trực tiếp.

Khóa/mở khóa tài khoản là chức năng bổ sung ngoài các mã ADM ở trên. Người dùng đã đăng nhập có thể đổi mật khẩu bằng mật khẩu hiện tại; thao tác này giữ nguyên session.

## Epic 1.6 — Sao lưu / Phục hồi

Admin mở **Sao lưu / Phục hồi** từ dashboard. Ứng dụng tạo bản sao lưu đầy đủ của `QLDSV` với tên `QLDSV_YYYYMMDD_HHMMSS_ffffff.bak`, liệt kê các file `.bak` và thời gian sửa đổi từ thư mục được cấu hình. SinhVien không có menu này và service từ chối lời gọi trực tiếp từ phiên không phải Admin.

Đặt `QLDSV_BACKUP_DIR` trong `.env` thành **đường dẫn tuyệt đối tới thư mục đã tồn tại**. Thư mục phải nhìn thấy được từ cả ứng dụng Python lẫn máy chạy SQL Server. Nếu SQL Server chạy trên máy khác, dùng thư mục chia sẻ UNC; không dùng ổ đĩa mạng được map riêng cho người dùng Windows. Tài khoản dịch vụ SQL Server cần quyền đọc/ghi file trong thư mục; tài khoản kết nối SQL cần quyền `BACKUP DATABASE` để sao lưu và quyền phù hợp để phục hồi (thường là `sysadmin`). SQL Server xử lý đường dẫn file sao lưu theo môi trường của dịch vụ SQL Server, không theo thư mục làm việc của ứng dụng.

Trước khi phục hồi, ứng dụng kiểm tra header để xác nhận file là bản sao lưu đầy đủ của `QLDSV`, chạy `RESTORE VERIFYONLY`, rồi yêu cầu Admin xác nhận. Phục hồi sẽ ngắt các kết nối đang dùng database và thay thế dữ liệu hiện tại. Sau khi hoàn tất, ứng dụng đưa database về `MULTI_USER` và trở lại màn hình đăng nhập. Nếu không cấu hình đường dẫn hoặc thiếu quyền, màn hình hiển thị lỗi bằng tiếng Việt. Không nên thử phục hồi trên `QLDSV` đang có dữ liệu cần giữ; hãy dùng database thử nghiệm độc lập để kiểm tra thao tác ghi này.

## Yêu cầu

- Python 3.10 trở lên
- SQL Server với database `QLDSV` và bảng `dbo.TaiKhoan`
- Microsoft ODBC Driver 17 hoặc 18 for SQL Server

## Cài đặt

Trong PowerShell tại thư mục repo:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Sửa `.env` để khớp cấu hình SQL Server. Mặc định dùng Windows Authentication, `localhost`, database `QLDSV` và ODBC Driver 17. Nếu dùng SQL Server Authentication, đặt `DB_TRUSTED_CONNECTION=no` và khai báo `DB_USERNAME`/`DB_PASSWORD`.

## Kiểm tra kết nối và chạy

```powershell
python -m app.config.database
python .\app\main.py
```

Có thể chạy tương đương bằng `python -m app.main`.

Tài khoản demo được seed trong database: `admin` / `123456`. Sinh viên mới cần tồn tại trong `dbo.Sinhvien` trước khi tạo tài khoản. Mật khẩu hiện được lưu plaintext theo cấu hình đồ án hiện tại.

## Cấu trúc

- `app/config/database.py`: đọc cấu hình và mở kết nối SQL Server
- `app/repositories/account_repository.py`: truy vấn `dbo.TaiKhoan`
- `app/services/auth_service.py`: xác thực và tạo session
- `app/services/account_service.py`: tạo/sửa tài khoản, kiểm tra liên kết và trạng thái
- `app/services/authorization.py`: kiểm tra quyền Admin và MASV của Sinh viên từ session
- `app/services/student_score_service.py`: cung cấp MASV của sinh viên hiện tại cho module điểm sau này
- `app/services/change_password_service.py`: xác thực mật khẩu hiện tại và cập nhật mật khẩu
- `app/services/backup_restore_service.py`: quyền Admin, kiểm tra thư mục/file và xử lý lỗi sao lưu/phục hồi
- `app/repositories/backup_restore_repository.py`: lệnh SQL Server `BACKUP`, kiểm tra file và `RESTORE`
- `app/ui/account_management.py`: danh sách và form quản lý tài khoản
- `app/ui/change_password.py`: form đổi mật khẩu
- `app/ui/backup_restore.py`: danh sách file sao lưu, tạo sao lưu và xác nhận phục hồi
- `app/ui/`: form đăng nhập và dashboard theo vai trò
- `app/utils/session.py`: session trong bộ nhớ
- `database/`: các script SQL hiện có, không bị thay đổi bởi milestone này
