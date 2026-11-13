"""Unit tests for Person 2 modules: Lop, Sinhvien, Monhoc, and Diem (Epics 2.1, 2.2, 2.3, 2.5)."""

from datetime import date, timedelta
import os
import unittest
from unittest.mock import MagicMock, Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pyodbc
from PySide6.QtWidgets import QApplication, QMessageBox

from app.models.diem import DiemSinhvienRow
from app.models.lop import Lop
from app.models.monhoc import Monhoc
from app.models.sinhvien import Sinhvien
from app.models.user import User
from app.services.account_service import AccountServiceError
from app.services.diem_service import DiemService, DiemServiceError
from app.services.lop_service import LopService, LopServiceError
from app.services.monhoc_service import MonhocService, MonhocServiceError
from app.services.sinhvien_service import SinhvienService, SinhvienServiceError
from app.ui.admin_dashboard import AdminDashboard
from app.ui.diem_management import DiemManagementDialog
from app.ui.lecturer_dashboard import LecturerDashboard
from app.ui.lop_management import LopManagementDialog
from app.ui.monhoc_management import MonhocManagementDialog
from app.ui.sinhvien_management import SinhvienManagementDialog
from app.utils import session

APP = QApplication.instance() or QApplication([])
ADMIN = User("GV00000001", "Admin", None, "GV00000001", True)
LECTURER = User("GV00000002", "GiangVien", None, "GV00000002", True)
STUDENT = User("SV00000001", "SinhVien", "SV00000001", None, True)


class _SessionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        session.clear_session()
        self.set_user(ADMIN)

    def tearDown(self) -> None:
        session.clear_session()

    @staticmethod
    def set_user(user: User | None) -> None:
        session.clear_session()
        if user is not None:
            conn = MagicMock()
            session.set_authenticated(user, conn)


class LopServiceTests(_SessionTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = Mock()
        self.repo.exists.return_value = False
        self.repo.exists_tenlop.return_value = False
        self.repo.has_students.return_value = False
        self.repo.has_assignments.return_value = False
        self.service = LopService(lop_repository=self.repo)

    def test_requires_admin(self) -> None:
        for non_admin in (None, LECTURER, STUDENT):
            self.set_user(non_admin)
            with self.assertRaises(PermissionError):
                self.service.find_all()
            with self.assertRaises(PermissionError):
                self.service.create("CNTT01", "Công nghệ thông tin 1")

    def test_create_validates_malop_and_tenlop(self) -> None:
        for invalid_malop in ("", "   ", "CNTT 01", "ABCDEFGHI"):
            with self.assertRaises(LopServiceError):
                self.service.create(invalid_malop, "Lớp hợp lệ")
        for invalid_tenlop in ("", "   ", "A" * 41):
            with self.assertRaises(LopServiceError):
                self.service.create("CNTT01", invalid_tenlop)

    def test_create_rejects_duplicate_malop_or_tenlop(self) -> None:
        self.repo.exists.return_value = True
        with self.assertRaises(LopServiceError):
            self.service.create("CNTT01", "Công nghệ thông tin 1")

        self.repo.exists.return_value = False
        self.repo.exists_tenlop.return_value = True
        with self.assertRaises(LopServiceError):
            self.service.create("CNTT01", "Công nghệ thông tin 1")

    def test_create_and_update_normalize_inputs(self) -> None:
        self.service.create(" cntt01 ", " Công nghệ thông tin 1 ")
        self.repo.create.assert_called_once_with("CNTT01", "Công nghệ thông tin 1")

        self.repo.exists.return_value = True
        self.service.update("cntt01", " Công nghệ thông tin 01 Mới ")
        self.repo.update.assert_called_once_with("CNTT01", "Công nghệ thông tin 01 Mới")

    def test_delete_blocks_when_class_has_students_or_assignments(self) -> None:
        self.repo.exists.return_value = True
        self.repo.has_students.return_value = True
        with self.assertRaises(LopServiceError):
            self.service.delete("CNTT01")
        self.repo.delete.assert_not_called()

        self.repo.has_students.return_value = False
        self.repo.has_assignments.return_value = True
        with self.assertRaises(LopServiceError):
            self.service.delete("CNTT01")
        self.repo.delete.assert_not_called()

        self.repo.has_assignments.return_value = False
        self.service.delete("CNTT01")
        self.repo.delete.assert_called_once_with("CNTT01")


class MonhocServiceTests(_SessionTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = Mock()
        self.repo.exists.return_value = False
        self.repo.exists_tenmh.return_value = False
        self.repo.has_grades.return_value = False
        self.repo.has_assignments.return_value = False
        self.service = MonhocService(monhoc_repository=self.repo)

    def test_validate_mamh_tenmh_and_credits(self) -> None:
        for bad_mamh in ("", "  ", "CS DL", "ABCDEF"):
            with self.assertRaises(MonhocServiceError):
                self.service.create(bad_mamh, "Cơ sở dữ liệu", 3, 1)
        for bad_tenmh in ("", "   ", "X" * 41):
            with self.assertRaises(MonhocServiceError):
                self.service.create("CSDL", bad_tenmh, 3, 1)
        for lt, th in ((-1, 0), (0, -1), (True, 1), (2, False)):
            with self.assertRaises(MonhocServiceError):
                self.service.create("CSDL", "Cơ sở dữ liệu", lt, th)

    def test_create_update_and_delete(self) -> None:
        self.service.create(" csdl ", " Cơ sở dữ liệu ", 3, 1)
        self.repo.create.assert_called_once_with("CSDL", "Cơ sở dữ liệu", 3, 1)

        self.repo.exists.return_value = True
        self.repo.has_grades.return_value = True
        with self.assertRaises(MonhocServiceError):
            self.service.delete("CSDL")
        self.repo.delete.assert_not_called()

        self.repo.has_grades.return_value = False
        self.service.delete("CSDL")
        self.repo.delete.assert_called_once_with("CSDL")


class SinhvienServiceTests(_SessionTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.sv_repo = Mock()
        self.lop_repo = Mock()
        self.acc_service = Mock()
        self.sv_repo.exists.return_value = False
        self.sv_repo.has_grades.return_value = False
        self.lop_repo.exists.return_value = True
        self.service = SinhvienService(
            sinhvien_repository=self.sv_repo,
            lop_repository=self.lop_repo,
            account_service=self.acc_service,
        )

    def test_find_by_lop_filters_by_keyword(self) -> None:
        s1 = Sinhvien("SV00000001", "Nguyễn Văn", "An", "CNTT01", True, date(2004, 1, 1), None, None, None, False, None)
        s2 = Sinhvien("SV00000002", "Trần Thị", "Bình", "CNTT01", False, date(2004, 2, 2), None, None, None, False, None)
        self.sv_repo.find_by_lop.return_value = [s1, s2]

        self.assertEqual(self.service.find_by_lop("cntt01", "bình"), [s2])
        self.assertEqual(self.service.find_by_lop("cntt01", "SV00000001"), [s1])
        self.assertEqual(len(self.service.find_by_lop("cntt01", "")), 2)

    def test_create_student_auto_creates_account_sv12(self) -> None:
        warning = self.service.create(
            masv="sv00000010",
            ho="Lê Văn",
            ten="Cường",
            malop="CNTT01",
            phai=True,
            ngaysinh=date(2004, 5, 15),
            noisinh="Hà Nội",
            diachi="123 Đường Láng",
            ghichu=None,
            nghihoc=False,
            hinh=None,
        )
        self.assertIsNone(warning)
        self.sv_repo.create.assert_called_once()
        self.acc_service.create_student_account.assert_called_once_with("SV00000010")

    def test_create_student_returns_warning_if_auto_account_fails(self) -> None:
        self.acc_service.create_student_account.side_effect = AccountServiceError("Login đã tồn tại")
        warning = self.service.create(
            masv="SV00000010",
            ho="Lê Văn",
            ten="Cường",
            malop="CNTT01",
        )
        self.assertIsNotNone(warning)
        self.assertIn("Login đã tồn tại", warning)

    def test_validate_ngaysinh_and_required_names(self) -> None:
        future_date = date.today() + timedelta(days=1)
        with self.assertRaises(SinhvienServiceError):
            self.service.create("SV00000010", "Lê", "Cường", "CNTT01", ngaysinh=future_date)
        with self.assertRaises(SinhvienServiceError):
            self.service.create("SV00000010", "", "Cường", "CNTT01")
        with self.assertRaises(SinhvienServiceError):
            self.service.create("SV00000010", "Lê", "", "CNTT01")

    def test_delete_blocks_when_student_has_grades(self) -> None:
        self.sv_repo.exists.return_value = True
        self.sv_repo.has_grades.return_value = True
        with self.assertRaises(SinhvienServiceError):
            self.service.delete("SV00000001")
        self.sv_repo.delete.assert_not_called()


class DiemServiceTests(_SessionTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = Mock()
        self.service = DiemService(diem_repository=self.repo)

    def test_permissions_allow_admin_and_lecturer_but_block_student(self) -> None:
        self.repo.get_lops_for_grading.return_value = [Lop("CNTT01", "CNTT 1")]
        self.set_user(ADMIN)
        self.assertEqual(len(self.service.get_lops_for_grading()), 1)

        self.set_user(LECTURER)
        self.assertEqual(len(self.service.get_lops_for_grading()), 1)

        self.set_user(STUDENT)
        with self.assertRaises(PermissionError):
            self.service.get_lops_for_grading()

    def test_parse_grade_rules(self) -> None:
        self.assertIsNone(DiemService.parse_grade(""))
        self.assertIsNone(DiemService.parse_grade("   "))
        self.assertEqual(DiemService.parse_grade("0"), 0.0)
        self.assertEqual(DiemService.parse_grade("10"), 10.0)
        self.assertEqual(DiemService.parse_grade("7.5"), 7.5)
        self.assertEqual(DiemService.parse_grade("8,25"), 8.25)

        for invalid in ("-0.1", "10.01", "abc", "11"):
            with self.assertRaises(DiemServiceError):
                DiemService.parse_grade(invalid, "SV00000001")

    def test_lan2_sql_error_54003_mapped_cleanly(self) -> None:
        self.repo.get_grading_list.side_effect = pyodbc.Error("42000", "[SQL Server] (54003) Chưa nhập lần 1")
        with self.assertRaises(DiemServiceError) as ctx:
            self.service.get_grading_list("CNTT01", "CSDL", 2)
        self.assertIn("lần thi 1", str(ctx.exception))

    def test_save_grades_validates_all_before_saving(self) -> None:
        with self.assertRaises(DiemServiceError):
            self.service.save_grades("CSDL", 1, [("SV00000001", "8.0"), ("SV00000002", "12.0")])
        self.repo.save_grades.assert_not_called()

        self.service.save_grades("CSDL", 1, [("SV00000001", "8.5"), ("SV00000002", "")])
        self.repo.save_grades.assert_called_once_with(
            "CSDL", 1, [("SV00000001", 8.5), ("SV00000002", None)]
        )


class Person2UiTests(_SessionTestCase):
    def test_dialogs_and_dashboard_wiring(self) -> None:
        lop_svc = Mock()
        lop_svc.find_all.return_value = [Lop("CNTT01", "Công nghệ thông tin 1")]
        mh_svc = Mock()
        mh_svc.find_all.return_value = [Monhoc("CSDL", "Cơ sở dữ liệu", 3, 1)]
        sv_svc = Mock()
        sv_svc.find_by_lop.return_value = [
            Sinhvien("SV00000001", "Nguyễn", "An", "CNTT01", True, date(2004, 1, 1), "HN", "HN", None, False, None)
        ]
        diem_svc = Mock()
        diem_svc.get_lops_for_grading.return_value = [Lop("CNTT01", "Công nghệ thông tin 1")]
        diem_svc.get_monhocs_for_grading.return_value = [Monhoc("CSDL", "Cơ sở dữ liệu", 3, 1)]
        diem_svc.get_grading_list.return_value = [DiemSinhvienRow("SV00000001", "Nguyễn", "An", 7.5)]

        lop_dlg = LopManagementDialog(lop_service=lop_svc)
        self.addCleanup(lop_dlg.close)
        self.assertEqual(lop_dlg.lop_table.rowCount(), 1)

        mh_dlg = MonhocManagementDialog(monhoc_service=mh_svc)
        self.addCleanup(mh_dlg.close)
        self.assertEqual(mh_dlg.monhoc_table.rowCount(), 1)

        sv_dlg = SinhvienManagementDialog(sinhvien_service=sv_svc, lop_service=lop_svc)
        self.addCleanup(sv_dlg.close)
        self.assertEqual(sv_dlg.sv_table.rowCount(), 1)

        diem_dlg = DiemManagementDialog(diem_service=diem_svc)
        self.addCleanup(diem_dlg.close)
        diem_dlg._start_grading()
        self.assertEqual(diem_dlg.diem_table.rowCount(), 1)
        with patch.object(QMessageBox, "information"):
            diem_dlg._save_grades()
        diem_svc.save_grades.assert_called_once_with("CSDL", 1, [("SV00000001", "7.5")])

        # Verify AdminDashboard and LecturerDashboard wiring
        admin_dash = AdminDashboard(
            ADMIN,
            lop_service=lop_svc,
            sinhvien_service=sv_svc,
            monhoc_service=mh_svc,
            diem_service=diem_svc,
        )
        self.addCleanup(admin_dash.close)
        for action, target_cls in (
            ("Quản lý sinh viên", "app.ui.admin_dashboard.SinhvienManagementDialog"),
            ("Quản lý môn học", "app.ui.admin_dashboard.MonhocManagementDialog"),
            ("Nhập điểm", "app.ui.admin_dashboard.DiemManagementDialog"),
        ):
            with patch(target_cls) as mock_dlg:
                admin_dash._handle_action(action)
                mock_dlg.assert_called_once()

        lec_dash = LecturerDashboard(LECTURER, diem_service=diem_svc)
        self.addCleanup(lec_dash.close)
        with patch("app.ui.lecturer_dashboard.DiemManagementDialog") as mock_diem_dlg:
            lec_dash._handle_action("Nhập điểm")
            mock_diem_dlg.assert_called_once()


if __name__ == "__main__":
    unittest.main()

