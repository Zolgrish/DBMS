"""Stored-procedure access for Admin PhanCong and Lecturer/Student self-service views."""

from app.utils import session


class RolePortalRepository:
    # --- Admin: PhanCong CRUD ---
    def find_all_phancong(self) -> list[tuple]:
        with session.qldsv_cursor() as cursor:
            return cursor.execute("EXEC dbo.sp_PhanCong_GetAll;").fetchall()

    def add_phancong(self, magv: str, malop: str, mamh: str) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute(
                "EXEC dbo.sp_PhanCong_Them @MAGV=?, @MALOP=?, @MAMH=?;",
                magv,
                malop,
                mamh,
            )

    def delete_phancong(self, magv: str, malop: str, mamh: str) -> None:
        with session.qldsv_cursor() as cursor:
            cursor.execute(
                "EXEC dbo.sp_PhanCong_Xoa @MAGV=?, @MALOP=?, @MAMH=?;",
                magv,
                malop,
                mamh,
            )

    # --- Lecturer: Own profile, assignments, students in assigned classes ---
    def get_lecturer_profile(self):
        with session.qldsv_cursor() as cursor:
            return cursor.execute("EXEC dbo.sp_GiangVien_XemHoSo;").fetchone()

    def get_lecturer_assignments(self) -> list[tuple]:
        with session.qldsv_cursor() as cursor:
            return cursor.execute("EXEC dbo.sp_GiangVien_XemPhanCong;").fetchall()

    def get_lecturer_class_students(self, malop: str) -> list[tuple]:
        with session.qldsv_cursor() as cursor:
            return cursor.execute(
                "EXEC dbo.sp_GiangVien_XemSinhVienLop @MALOP=?;",
                malop,
            ).fetchall()

    # --- Student: Own profile, class, subjects, own grades ---
    def get_student_profile_and_class(self):
        with session.qldsv_cursor() as cursor:
            return cursor.execute("EXEC dbo.sp_SinhVien_XemHoSoVaLop;").fetchone()

    def get_student_subjects(self) -> list[tuple]:
        with session.qldsv_cursor() as cursor:
            return cursor.execute("EXEC dbo.sp_SinhVien_XemMonHoc;").fetchall()

    def get_student_own_grades(self) -> list[tuple]:
        with session.qldsv_cursor() as cursor:
            return cursor.execute("EXEC dbo.sp_SinhVien_XemDiem;").fetchall()

