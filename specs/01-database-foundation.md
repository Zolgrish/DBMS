# 01 - Database Foundation

**Owner chính:** Người 1  
**Tickets:** DB-01..DB-09, SP-01..SP-09

## Schema

### `Lop`

- `MALOP NCHAR(8)` - PK.
- `TENLOP NVARCHAR(40)` - UNIQUE.

### `Sinhvien`

- `MASV NCHAR(10)` - PK.
- `HO NVARCHAR(40)`.
- `TEN NVARCHAR(10)`.
- `MALOP NCHAR(8)` - FK -> `Lop`.
- `PHAI BIT` - default `1`.
- `NGAYSINH DATETIME`.
- `NOISINH NVARCHAR(40)`.
- `DIACHI NVARCHAR(80)`.
- `GHICHU TEXT` theo cấu trúc đề.
- `NGHIHOC BIT` - default `0`.
- `HINH NVARCHAR(1000)`.

### `Giangvien`

- `MAGV NCHAR(10)` - PK.
- `HO NVARCHAR(40)`.
- `TEN NVARCHAR(10)`.
- `PHAI BIT` - default `1`.

### `Monhoc`

- `MAMH NCHAR(5)` - PK.
- `TENMH NVARCHAR(40)` - UNIQUE.
- `SoTCLT INT` - `>= 0`.
- `SoTCTH INT` - `>= 0`.

### `Diem`

- `MASV NCHAR(10)` - FK -> `Sinhvien`.
- `MAMH NCHAR(5)` - FK -> `Monhoc`.
- `LAN SMALLINT` - chỉ `1..2`.
- `DIEM FLOAT` - `0..10`; việc cho `NULL` phụ thuộc quyết định `NULL = vắng`.
- PK ghép `(MASV, MAMH, LAN)`.

## Constraint requirements

**DB-07/DB-08:** FK, UNIQUE, DEFAULT và CHECK phải nằm trong SQL Server. UI validation có thể lặp lại để UX tốt hơn nhưng không thay thế DB constraint.

## Bảng bổ trợ `PhanCong`

Repository hiện có `database/CreatePhanCong.sql`. Script này phải được giữ trong bootstrap database và chạy sau khi 5 bảng cốt lõi đã tồn tại.

`PhanCong` có PK ghép `(MAGV, MALOP, MAMH)` và FK tới `Giangvien`, `Lop`, `Monhoc`. Đây là bảng bổ trợ cho phân công giảng dạy, không phải bảng account và không thay đổi kiến trúc Security.

## Seed data - DB-09

Seed phải đủ để test ít nhất:

- sinh viên đang học;
- sinh viên nghỉ học;
- chưa nhập điểm lần 1;
- điểm lần 1 đạt;
- điểm lần 1 < 5;
- trường hợp vắng nếu nhóm chốt cách biểu diễn;
- có điểm lần 2 để test hiệu chỉnh/MAX.

## Common Stored Procedures

| Ticket | SP | Yêu cầu |
|---|---|---|
| SP-01 | `sp_GetLop` | Lấy danh sách lớp |
| SP-02 | `sp_GetMonHoc` | Lấy danh sách môn |
| SP-03 | `sp_GetGiangVien` | Lấy danh sách giảng viên |
| SP-04 | `sp_GetSinhVienByLop` | Lấy SV theo lớp; CRUD có thể gồm SV nghỉ học |
| SP-05 | `sp_GetSinhVienByMa` | Tra cứu 1 SV |
| SP-06 | `sp_CheckMaSV` | Kiểm tra MASV tồn tại/trùng |
| SP-07 | `sp_CheckMaLop` | Kiểm tra lớp tồn tại |
| SP-08 | `sp_CheckMaMH` | Kiểm tra môn tồn tại |
| SP-09 | `sp_GetActiveStudents` | Chỉ SV `NGHIHOC = 0`; dùng cho nghiệp vụ chính |

## Acceptance checklist

- Script chạy được trên SQL Server 2014.
- Tất cả constraint quan trọng được DB enforce.
- SP-09 không trả SV nghỉ học.
- Seed data tái tạo được các case test chính.
- Không thêm `dbo.TaiKhoan` vào schema foundation.
