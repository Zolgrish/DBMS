# QLDSV desktop application

Ứng dụng Python/PySide6 cho hệ thống quản lý điểm sinh viên. Milestone này triển khai AUTH-01 đến AUTH-06: đăng nhập, kiểm tra tài khoản trong `dbo.TaiKhoan`, tạo session, điều hướng theo vai trò và đăng xuất. Các dashboard mới có menu khung; nghiệp vụ trên từng menu sẽ được bổ sung ở các milestone tiếp theo.

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

Tài khoản demo được seed trong database: `admin` / `123456`. Mật khẩu hiện được lưu plaintext theo cấu hình đồ án hiện tại.

## Cấu trúc

- `app/config/database.py`: đọc cấu hình và mở kết nối SQL Server
- `app/repositories/account_repository.py`: truy vấn `dbo.TaiKhoan`
- `app/services/auth_service.py`: xác thực và tạo session
- `app/ui/`: form đăng nhập và dashboard theo vai trò
- `app/utils/session.py`: session trong bộ nhớ
- `database/`: các script SQL hiện có, không bị thay đổi bởi milestone này
