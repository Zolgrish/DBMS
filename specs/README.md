# QLDSV Specs

Thư mục này chuyển backlog revised thành đặc tả triển khai cho repository `D:\\DBMS`.

## Thứ tự đọc

| File | Phạm vi | Backlog chính |
|---|---|---|
| `00-project-scope.md` | Phạm vi đồ án, role, quy tắc toàn cục, open decisions | Toàn dự án |
| `01-database-foundation.md` | 5 bảng, constraint, seed, common SP | DB-01..09, SP-01..09 |
| `02-security-authentication.md` | SSMS Security, Login/User/Role, **ma trận quyền chuẩn 3 role**, login app, connection theo user | SEC-01..07, AUTH-01..08 |
| `03-account-password.md` | SP tạo/xóa account, quản trị account, đổi SQL Login password | SECSP-01..06, ADM-01..07, PASS-01..05 |
| `04-backup-restore.md` | Backup/Restore và quyền liên quan | BAK-01..08 |
| `05-crud-student-integration.md` | CRUD Người 2 và tích hợp SQL account khi thêm/xóa SV | LOP, SV, MH, GV |
| `06-grading.md` | Nhập điểm lần 1/2, transaction, nghỉ học, vắng | DIEM, D1, D2 |
| `07-reporting.md` | 5 nhóm báo cáo và logic tổng hợp | RPT-01..36 |
| `08-integration-test-plan.md` | Merge/integration và test security end-to-end | INT-01..17 |

## Nguyên tắc

- `specs/` mô tả **kiến trúc mục tiêu**, không mô tả code legacy hiện tại.
- Ma trận quyền chuẩn của `Admin` / `GiangVien` / `SinhVien` nằm tại `02-security-authentication.md`; các spec khác phải tham chiếu và không được nới rộng quyền trái ma trận này.
- Khi implementation và spec mâu thuẫn, không sửa spec để hợp thức hóa code cũ; phải xác minh yêu cầu trước.
- Ticket ID trong spec giữ nguyên theo backlog revised để dễ chia việc và review.
- Open decision phải được ghi rõ; agent không tự chốt ngầm.

