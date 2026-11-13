# 06 - Grading / Nhập điểm

**Owner chính:** Người 2  
**Tickets:** DIEM-01..10, D1-01..04, D2-01..05

## Flow

`Lớp -> Môn học -> Lần thi -> Bắt đầu -> Grid nhập điểm`

Grid:

- `MASV` read-only;
- Họ tên read-only;
- Điểm editable theo rule.

Chỉ sinh viên `NGHIHOC = 0` xuất hiện trong nghiệp vụ nhập điểm.

## Validation

- Lần thi chỉ `1` hoặc `2`.
- Điểm số chỉ `0..10`.
- Nếu nhóm chốt `NULL = vắng`, UI và DB phải cùng hiểu quy ước này.
- Save hàng loạt phải trong transaction; lỗi giữa chừng rollback toàn bộ batch.

## Lần thi 1

- **D1-01:** chưa có điểm -> hiện toàn bộ SV đang học của lớp, cột điểm trống.
- **D1-02:** đã có điểm -> load lại giá trị cũ.
- **D1-03:** cho hiệu chỉnh và lưu lại.
- **D1-04:** điểm không hợp lệ -> không ghi.

## Lần thi 2

- **D2-01:** chưa nhập lần 1 -> báo lỗi, không mở danh sách nhập lần 2.
- **D2-02:** đã có lần 1, chưa có lần 2 -> chỉ hiện SV lần 1 `< 5` hoặc vắng.
- **D2-03:** đã có lần 2 -> load điểm lần 2 để hiệu chỉnh.
- **D2-04:** SV lần 1 đạt -> không xuất hiện ở lần 2.
- **D2-05:** save `LAN = 2` theo transaction.

## Open decision - vắng

Đề có “vắng” nhưng `DIEM` là `float`. Không tự chốt quy ước nếu nhóm chưa xác nhận. Khi chốt `NULL = vắng`, cần cập nhật đồng bộ:

- CHECK constraint;
- form nhập điểm;
- query lần 2;
- report;
- seed/test data.

## Ranh giới quyền GiangVien

QLDSV_GIANGVIEN -> GiangVien; DatabaseUser/Username = Giangvien.MAGV có sẵn, còn LoginName là credential server có thể khác tên và map bằng SID. QLDSV_ADMIN cũng gắn MAGV, QLDSV_SINHVIEN gắn MASV. Mỗi User đúng một role. Account Management chỉ cấp account cho entity có sẵn, không INSERT business person.

Quyền grading mục tiêu:

| Nghiệp vụ điểm | Admin | GiangVien | SinhVien |
|---|---|---|---|
| Xem tất cả điểm | Allow | Deny | Deny |
| Xem điểm lớp/môn phụ trách | Allow | Allow theo `PhanCong` | Deny |
| Xem điểm bản thân | Allow | — | Allow |
| Nhập điểm | Allow | Allow theo `PhanCong` | Deny |
| Sửa điểm | Allow | Allow theo `PhanCong` | Deny |
| Xóa điểm | Allow | Deny | Deny |

GiangVien không có server admin roles, master connection, Account Management hoặc Backup/Restore. SP grading phải suy MAGV từ SQL principal tin cậy và kiểm tra `dbo.PhanCong(MAGV,MALOP,MAMH)` trước khi trả danh sách điểm, nhập hoặc sửa. Không nhận MAGV tùy ý từ UI, không enforce chỉ bằng UI và không cấp schema-wide EXECUTE.

`Xóa điểm` là quyền Admin-only. GiangVien dù được phân công đúng lớp/môn vẫn phải bị SQL Server từ chối xóa. SinhVien chỉ xem điểm bản thân qua SP suy MASV từ principal hiện tại.
