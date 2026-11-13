# 04 - Backup & Restore

**Owner chính:** Người 1  
**Tickets:** BAK-01..BAK-08

## BAK-01 - Access

- Chỉ Admin có menu/form Backup/Restore.
- GiangVien và Student bị từ chối ở cả UI lẫn SQL Server.

## BAK-02 - Backup

- Tạo full backup `.bak` thành công.
- Đường dẫn backup phải là nơi SQL Server service có quyền ghi.
- Lỗi path/permission phải báo rõ, không crash.

## BAK-03 - Backup history

Nên hiển thị lịch sử từ `msdb.dbo.backupset` hoặc nguồn SQL Server tương đương, tối thiểu có:

- ngày/giờ;
- position hoặc identifier cần để restore;
- user thực hiện nếu nguồn dữ liệu cung cấp.

## BAK-04/05 - Restore

- Admin chọn bản backup và yêu cầu restore.
- Phải confirm trước khi thay dữ liệu hiện tại.
- Restore thực hiện từ context phù hợp như `master`, không giữ connection đang sử dụng `QLDSV` theo cách làm restore fail.
- Sau restore phải đưa ứng dụng/database về trạng thái dùng được hoặc báo lỗi rõ.

## BAK-06 - Permission proof

Backup/Restore phải được test bằng **Admin login thật** đã cấu hình quyền trong SSMS. Không dùng `sa` làm đường tắt cho demo.

## BAK-07 - Non-Admin denial

GiangVien và Student:

- không có menu;
- gọi service trực tiếp vẫn fail;
- SQL principal cũng không có permission thực thi backup/restore.

## BAK-08 - Error handling

Phải xử lý ít nhất:

- file/path sai;
- permission filesystem/SQL sai;
- backup file không hợp lệ;
- database đang bị sử dụng;
- restore thất bại giữa chừng.

## Safety

Không chạy restore destructive trên database có dữ liệu cần giữ. Test bằng DB/demo data được phép thay thế.

