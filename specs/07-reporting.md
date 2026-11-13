# 07 - Reporting

**Owner chính:** Người 3  
**Tickets:** RPT-01..RPT-36

Các report phải chạy dưới principal hiện tại và tuân theo ma trận quyền tại `02-security-authentication.md`:

- Admin được dùng report/quyền xem quản trị trong phạm vi toàn hệ thống.
- GiangVien chỉ được xem dữ liệu lớp, sinh viên, môn và điểm thuộc `dbo.PhanCong` của chính MAGV; không được dùng report để vượt scope.
- SinhVien không gọi report quản trị; màn hình cá nhân chỉ được xem lớp/môn/điểm của chính mình qua SP/query suy từ MASV hiện tại.

## 3.1 - Danh sách Sinh viên (RPT-01..08)

Input: lớp.  
Output gồm lớp, ngày in, STT, MASV, họ tên, phái, ngày sinh, ghi chú, tổng số SV.

Chỉ lấy sinh viên đang học.

## 3.2 - Danh sách thi hết môn (RPT-09..15)

Input: lớp, môn, ngày thi, lần thi.

Lần 2 chỉ gồm sinh viên lần 1 chưa đạt/chưa thi theo quy ước nghiệp vụ đã chốt.

## 3.3 - Bảng điểm môn học (RPT-16..21)

Input: lớp, môn, lần thi.  
Output: STT, MASV, họ tên, điểm đúng lần thi.

## 3.4 - Phiếu điểm Sinh viên (RPT-22..28)

- Chọn/nhập MASV cho chức năng quản trị.
- Điểm môn = `MAX` giữa lần 1 và lần 2 nếu có.
- Tính ĐTB và xếp loại theo ngưỡng đề.
- Quy tắc tính ĐTB vẫn là open decision: chưa tự chọn trung bình cộng hay trọng số tín chỉ.

Ngưỡng xếp loại:

| ĐTB | Xếp loại |
|---|---|
| `< 5` | Yếu |
| `>= 5` và `< 7` | Trung bình |
| `>= 7` và `< 8` | Khá |
| `>= 8` và `< 9` | Giỏi |
| `>= 9` và `<= 10` | Xuất sắc |

## 3.5 - Bảng điểm tổng kết (RPT-29..36)

Input: lớp.  
Output dạng ma trận `MASV | Họ tên | Môn 1 | ... | Môn n`.

Mỗi ô điểm dùng `MAX` giữa hai lần thi. Số môn thay đổi nên report cần hỗ trợ cột động/dynamic pivot hoặc kỹ thuật tương đương.

## Student score view

Màn hình Student không được tái sử dụng report quản trị bằng cách truyền MASV tùy ý. Phải dùng SP student-specific trong spec security để chỉ trả dữ liệu của principal hiện tại.

