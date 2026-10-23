"""Local-only lecturer business CRUD, UI boundaries and SQL locking contracts."""

import os
from pathlib import Path
import re
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pyodbc
from PySide6.QtWidgets import QApplication, QAbstractItemView, QComboBox, QDialog, QLabel, QLineEdit, QMessageBox, QPushButton

from app.config import database
from app.models.lecturer import Lecturer
from app.models.user import User
from app.repositories.lecturer_repository import LecturerRepository
from app.services.lecturer_service import LecturerService, LecturerServiceError
from app.ui.admin_dashboard import AdminDashboard
from app.ui.lecturer_dashboard import LecturerDashboard
from app.ui.student_dashboard import StudentDashboard
from app.ui.lecturer_management import LecturerFormDialog, LecturerManagementDialog
from app.utils import session


ROOT = Path(__file__).resolve().parents[1]
ADMIN = User("GV00000001", "Admin", None, "GV00000001", True)
LECTURER = Lecturer("GV00000004", "Nguyễn", "An", True)


class Cursor:
    def __init__(self, rows=(), error=None):
        self.rows, self.error, self.calls, self.closed = list(rows), error, [], 0

    def execute(self, sql, *args):
        self.calls.append((sql, args))
        if self.error:
            raise self.error
        return self

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed += 1


class Connection:
    def __init__(self, rows=(), error=None):
        self.statement, self.closed = Cursor(rows, error), 0

    def cursor(self):
        return self.statement

    def close(self):
        self.closed += 1


class LecturerRepositoryTests(unittest.TestCase):
    def tearDown(self):
        session.clear_session()

    def test_listing_maps_common_sp_rows_and_trims_nchar(self):
        connection = Connection([("GV00000004  ", "Nguyễn", "An", 1), ("GV00000005", None, None, 0)])
        session.set_authenticated(ADMIN, connection)
        with patch.object(database.pyodbc, "connect") as connect:
            rows = LecturerRepository().find_all()
        connect.assert_not_called()
        self.assertEqual(rows, [LECTURER, Lecturer("GV00000005", None, None, False)])
        self.assertEqual(connection.statement.calls, [("EXEC dbo.sp_GetGiangVien;", ())])
        self.assertEqual((connection.closed, connection.statement.closed), (0, 1))

    def test_mutations_use_only_their_parameterized_procedures(self):
        for method, proc, args in (
            ("create", "sp_ThemGiangVien", ("GV00000004", "O'Brien; --", None, True)),
            ("update", "sp_CapNhatGiangVien", ("GV00000004", None, "An", False)),
            ("delete", "sp_XoaGiangVien", ("GV00000004",)),
        ):
            with self.subTest(method=method):
                connection = Connection()
                session.set_authenticated(ADMIN, connection)
                with patch.object(database.pyodbc, "connect") as connect:
                    getattr(LecturerRepository(), method)(*args)
                connect.assert_not_called()
                self.assertEqual(len(connection.statement.calls), 1)
                sql, parameters = connection.statement.calls[0]
                self.assertTrue(sql.startswith("EXEC dbo." + proc))
                self.assertEqual(parameters, args)
                self.assertEqual(sql.count("?"), len(args))
                self.assertNotIn("O'Brien", sql)
                self.assertNotIn("sp_TaoTaiKhoan", sql)
                self.assertEqual((connection.closed, connection.statement.closed), (0, 1))

    def test_no_session_never_connects(self):
        session.clear_session()
        with patch.object(database.pyodbc, "connect") as connect:
            with self.assertRaises(session.SessionRequiredError):
                LecturerRepository().find_all()
        connect.assert_not_called()

    def test_repository_propagates_sql_denial_and_closes_cursor(self):
        connection = Connection(error=pyodbc.Error("42000", "denied (229)"))
        session.set_authenticated(ADMIN, connection)
        with self.assertRaises(pyodbc.Error):
            LecturerRepository().delete("GV00000004")
        self.assertEqual((connection.closed, connection.statement.closed), (0, 1))


class LecturerServiceTests(unittest.TestCase):
    def setUp(self):
        session.set_current_user(ADMIN)
        self.repository = Mock(spec=LecturerRepository)
        self.service = LecturerService(self.repository)

    def tearDown(self):
        session.clear_session()

    def test_guest_student_and_lecturer_denied_before_repository_access(self):
        for user in (None, User("SV00000002", "SinhVien", "SV00000002", None, True),
                     User("GV00000002", "GiangVien", None, "GV00000002", True)):
            session.set_current_user(user) if user else session.clear_session()
            for method, args in (("find_all_lecturers", ()), ("create_lecturer", ("GV00000004",)),
                                 ("update_lecturer", ("GV00000004",)), ("delete_lecturer", ("GV00000004",))):
                with self.subTest(role=user.role if user else "guest", method=method):
                    with self.assertRaises(PermissionError):
                        getattr(self.service, method)(*args)
        self.assertEqual(self.repository.mock_calls, [])

    def test_admin_can_list_create_update_delete_without_account_operations(self):
        self.repository.find_all.return_value = [LECTURER]
        with patch("app.services.account_service.AccountService.create_account") as create_account:
            self.assertEqual(self.service.find_all_lecturers(), [LECTURER])
            self.service.create_lecturer("gv00000004", " Nguyễn ", "An", True)
            self.service.update_lecturer("gv00000004", None, "Bình", False)
            self.service.delete_lecturer("gv00000004")
        create_account.assert_not_called()
        self.repository.create.assert_called_once_with("GV00000004", "Nguyễn", "An", True)
        self.repository.update.assert_called_once_with("GV00000004", None, "Bình", False)
        self.repository.delete.assert_called_once_with("GV00000004")

    def test_invalid_magv_in_all_mutations_is_rejected(self):
        for magv in (None, "", "GV004", " GV0000004", "GV0000004 ", "GV00000004 ", "\u2003V00000004", "x" * 11, "😀" * 6):
            for method in (self.service.create_lecturer, self.service.update_lecturer, self.service.delete_lecturer):
                with self.subTest(magv=magv, method=method.__name__):
                    with self.assertRaises(LecturerServiceError):
                        method(magv)
        self.assertEqual(self.repository.mock_calls, [])

    def test_magv_length_is_utf16_units(self):
        self.service.create_lecturer("😀" * 5)
        self.repository.create.assert_called_once_with("😀" * 5, None, None, True)

    def test_field_limits_use_sql_nvarchar_capacity(self):
        for ho, ten in (("x" * 41, None), (None, "x" * 11), ("😀" * 21, None), (None, "😀" * 6)):
            for method in (self.service.create_lecturer, self.service.update_lecturer):
                with self.subTest(ho=ho, ten=ten):
                    with self.assertRaises(LecturerServiceError):
                        method("GV00000004", ho, ten, True)
        self.repository.create.assert_not_called()
        self.repository.update.assert_not_called()
        self.service.create_lecturer("GV00000004", "x" * 40, "x" * 10, False)
        self.repository.create.assert_called_once()

    def test_nullable_and_blank_names_are_supported(self):
        self.service.create_lecturer("GV00000004", "  ", "", True)
        self.repository.create.assert_called_once_with("GV00000004", None, None, True)

    def test_invalid_phai_rejected(self):
        for phai in (None, 2, -1, "Nam", 0.0):
            with self.subTest(phai=phai):
                with self.assertRaises(LecturerServiceError):
                    self.service.create_lecturer("GV00000004", phai=phai)
        self.repository.create.assert_not_called()

    def test_all_known_sql_errors_are_safe(self):
        for number in range(53001, 53010):
            self.repository.delete.side_effect = pyodbc.Error("42000", f"private-driver-details ({number})")
            with self.subTest(number=number), patch("logging.exception") as log:
                with self.assertRaises(LecturerServiceError) as caught:
                    self.service.delete_lecturer("GV00000004")
                self.assertEqual(str(caught.exception), self.service.SQL_ERRORS[number])
                self.assertNotIn("private-driver-details", str(caught.exception))
                log.assert_not_called()
        self.assertIn("Quản lý tài khoản", self.service.SQL_ERRORS[53006])
        self.assertIn("PhanCong", self.service.SQL_ERRORS[53007])

    def test_unknown_sql_error_is_safe(self):
        self.repository.find_all.side_effect = pyodbc.Error("42000", "private-driver-details")
        with self.assertRaises(LecturerServiceError) as caught:
            self.service.find_all_lecturers()
        self.assertNotIn("private-driver-details", str(caught.exception))

    def test_missing_session_is_translated_for_all_operations(self):
        for method, repository_method, args in (
            ("find_all_lecturers", "find_all", ()),
            ("create_lecturer", "create", ("GV00000004",)),
            ("update_lecturer", "update", ("GV00000004",)),
            ("delete_lecturer", "delete", ("GV00000004",)),
        ):
            getattr(self.repository, repository_method).side_effect = session.SessionRequiredError("lost")
            with self.subTest(method=method), self.assertRaisesRegex(LecturerServiceError, "đăng nhập lại"):
                getattr(self.service, method)(*args)

    def test_connection_loss_invalidates_session_without_reconnecting(self):
        for operation, args in (("find_all_lecturers", ()), ("create_lecturer", ("GV00000004",)),
                                ("update_lecturer", ("GV00000004",)), ("delete_lecturer", ("GV00000004",))):
            connection, master = Connection(error=pyodbc.Error("08S01", "lost")), Connection()
            session.set_authenticated(ADMIN, connection, master)
            with self.subTest(operation=operation), patch.object(database.pyodbc, "connect") as connect:
                with self.assertRaisesRegex(LecturerServiceError, "đăng nhập lại"):
                    getattr(LecturerService(), operation)(*args)
                connect.assert_not_called()
            self.assertIsNone(session.current_user)
            self.assertEqual((connection.closed, master.closed), (1, 1))


class LecturerUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        session.set_current_user(ADMIN)
        self.service = Mock(spec=LecturerService)
        self.service.find_all_lecturers.return_value = [LECTURER, Lecturer("GV00000005", None, "Lan", False)]

    def tearDown(self):
        session.clear_session()
        self.application.processEvents()

    def dialog(self):
        dialog = LecturerManagementDialog(self.service)
        self.addCleanup(dialog.close)
        return dialog

    def test_add_form_only_contains_business_fields(self):
        form = LecturerFormDialog(lambda values: None)
        self.addCleanup(form.close)
        self.assertEqual({v.objectName() for v in form.findChildren(QLineEdit)},
                         {"lecturerMagvInput", "lecturerHoInput", "lecturerTenInput"})
        self.assertEqual([v.objectName() for v in form.findChildren(QComboBox)], ["lecturerPhaiCombo"])
        self.assertEqual([v.text() for v in form.findChildren(QLabel)], ["MAGV", "Họ", "Tên", "Phái"])
        self.assertFalse(form.magv_input.isReadOnly())
        form.magv_input.setText("gv00000004")
        self.assertEqual(form.magv_input.text(), "GV00000004")
        self.assertTrue(all(v.echoMode() == QLineEdit.EchoMode.Normal for v in form.findChildren(QLineEdit)))
        self.assertEqual([form.phai_combo.itemText(i) for i in range(form.phai_combo.count())], ["Nam", "Nữ"])

    def test_edit_form_retains_original_magv_even_if_text_changed_programmatically(self):
        received = []
        form = LecturerFormDialog(received.append, LECTURER)
        self.addCleanup(form.close)
        self.assertTrue(form.magv_input.isReadOnly())
        form.magv_input.setText("GV99999999")
        form.ho_input.setText("Trần")
        form.ten_input.setText("Bình")
        form.phai_combo.setCurrentIndex(1)
        form._save()
        self.assertEqual(received, [dict(magv=LECTURER.magv, ho="Trần", ten="Bình", phai=False)])

    def test_form_validation_failure_remains_open_with_safe_message(self):
        save = Mock(side_effect=LecturerServiceError("MAGV không hợp lệ"))
        form = LecturerFormDialog(save)
        self.addCleanup(form.close)
        with patch.object(QMessageBox, "warning") as warning:
            form._save()
        self.assertNotEqual(form.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(warning.call_args.args[2], "MAGV không hợp lệ")

    def test_table_gender_buttons_and_selection(self):
        dialog = self.dialog()
        self.assertEqual(dialog.HEADERS, ("MAGV", "Họ", "Tên", "Phái"))
        self.assertEqual([dialog.lecturer_table.item(row, 3).text() for row in (0, 1)], ["Nam", "Nữ"])
        self.assertEqual([b.text() for b in dialog.findChildren(QPushButton)],
                         ["Thêm giảng viên", "Sửa giảng viên", "Xóa giảng viên", "Đóng"])
        self.assertEqual(dialog.lecturer_table.editTriggers(), QAbstractItemView.EditTrigger.NoEditTriggers)
        self.assertEqual(dialog.lecturer_table.selectionMode(), QAbstractItemView.SelectionMode.SingleSelection)

    def test_create_refreshes_table(self):
        dialog = self.dialog()
        added = Lecturer("GV00000006", "Lê", "Hoa", False)
        self.service.find_all_lecturers.return_value = [LECTURER, added]
        with patch("app.ui.lecturer_management.LecturerFormDialog") as form_class:
            def save():
                form_class.call_args.args[0](dict(magv=added.magv, ho=added.ho, ten=added.ten, phai=added.phai))
                return QDialog.DialogCode.Accepted
            form_class.return_value.exec.side_effect = save
            dialog.add_button.click()
        self.service.create_lecturer.assert_called_once_with(magv=added.magv, ho=added.ho, ten=added.ten, phai=False)
        self.assertEqual(self.service.find_all_lecturers.call_count, 2)
        self.assertEqual(dialog.lecturer_table.item(1, 0).text(), added.magv)

    def test_update_refreshes_table(self):
        dialog = self.dialog()
        dialog.lecturer_table.selectRow(0)
        self.service.find_all_lecturers.return_value = [Lecturer(LECTURER.magv, "Lê", "Bình", False)]
        with patch("app.ui.lecturer_management.LecturerFormDialog") as form_class:
            def save():
                self.assertEqual(form_class.call_args.kwargs["lecturer"], LECTURER)
                form_class.call_args.args[0](dict(magv=LECTURER.magv, ho="Lê", ten="Bình", phai=False))
                return QDialog.DialogCode.Accepted
            form_class.return_value.exec.side_effect = save
            dialog.edit_button.click()
        self.service.update_lecturer.assert_called_once_with(magv=LECTURER.magv, ho="Lê", ten="Bình", phai=False)
        self.assertEqual(self.service.find_all_lecturers.call_count, 2)
        self.assertEqual(dialog.lecturer_table.item(0, 2).text(), "Bình")

    def test_delete_requires_selection_and_confirmation_with_name(self):
        dialog = self.dialog()
        with patch.object(QMessageBox, "information") as info, patch.object(QMessageBox, "question") as question:
            dialog._delete_lecturer()
        info.assert_called_once()
        question.assert_not_called()
        dialog.lecturer_table.selectRow(0)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as question:
            dialog.delete_button.click()
        self.assertIn(LECTURER.magv, question.call_args.args[2])
        self.assertIn("Nguyễn An", question.call_args.args[2])
        self.service.delete_lecturer.assert_not_called()
        self.assertEqual(self.service.find_all_lecturers.call_count, 1)

    def test_confirmed_delete_refreshes_table(self):
        dialog = self.dialog()
        dialog.lecturer_table.selectRow(0)
        self.service.find_all_lecturers.return_value = []
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.delete_button.click()
        self.service.delete_lecturer.assert_called_once_with(LECTURER.magv)
        self.assertEqual(dialog.lecturer_table.rowCount(), 0)
        self.assertEqual(self.service.find_all_lecturers.call_count, 2)

    def test_delete_account_or_assignment_error_is_displayed_and_not_refreshed(self):
        dialog = self.dialog()
        dialog.lecturer_table.selectRow(0)
        for number in (53006, 53007):
            self.service.delete_lecturer.side_effect = LecturerServiceError(LecturerService.SQL_ERRORS[number])
            with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), patch.object(QMessageBox, "warning") as warning:
                dialog.delete_button.click()
            self.assertEqual(warning.call_args.args[2], LecturerService.SQL_ERRORS[number])
        self.assertEqual(self.service.find_all_lecturers.call_count, 1)

    def test_ui_handles_session_loss_on_initial_load(self):
        session.set_current_user(ADMIN)
        with patch.object(QMessageBox, "critical") as critical:
            dialog = LecturerManagementDialog(LecturerService())
        self.addCleanup(dialog.close)
        self.assertIn("đăng nhập lại", critical.call_args.args[2])
        self.assertEqual(dialog.lecturer_table.rowCount(), 0)

    def test_dashboard_order_injection_and_other_role_menus(self):
        account_service = Mock()
        admin = AdminDashboard(ADMIN, account_service, lecturer_service=self.service)
        self.addCleanup(admin.close)
        self.assertIs(admin._account_service, account_service)
        labels = [b.text() for b in admin.findChildren(QPushButton) if b.objectName() == "actionButton"]
        self.assertEqual(labels, ["Quản lý sinh viên", "Quản lý giảng viên", "Quản lý môn học", "Quản lý tài khoản",
                                  "Nhập điểm", "Đổi mật khẩu", "Sao lưu / Phục hồi"])
        with patch("app.ui.admin_dashboard.LecturerManagementDialog") as dialog_class:
            admin._handle_action("Quản lý giảng viên")
        dialog_class.assert_called_once_with(lecturer_service=self.service, parent=admin)
        dialog_class.return_value.exec.assert_called_once()
        dialog_class.return_value.deleteLater.assert_called_once()
        for cls, user in ((LecturerDashboard, User("GV00000002", "GiangVien", None, "GV00000002", True)),
                          (StudentDashboard, User("SV00000002", "SinhVien", "SV00000002", None, True))):
            dashboard = cls(user)
            self.addCleanup(dashboard.close)
            self.assertNotIn("Quản lý giảng viên", [b.text() for b in dashboard.findChildren(QPushButton)])


class LecturerSqlContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = (ROOT / "database/StoredProcedures_Lecturer.sql").read_text(encoding="utf-8")
        cls.bodies = {name: re.search(r"CREATE PROCEDURE dbo\." + name + r"\b(.*?)\nGO", cls.sql, re.S).group(1)
                      for name in ("sp_ThemGiangVien", "sp_CapNhatGiangVien", "sp_XoaGiangVien")}

    def test_each_mutation_has_independent_fail_closed_admin_mapping_guard(self):
        for body in self.bodies.values():
            guard = body[:body.index("BEGIN TRY")]
            for role, expected in (("ADMIN", 1), ("GIANGVIEN", 0), ("SINHVIEN", 0)):
                self.assertIn(f"ISNULL(IS_ROLEMEMBER(N'QLDSV_{role}'),-1)<>{expected}", guard)
            for text in ("ORIGINAL_LOGIN()<>SUSER_SNAME()", "USER_NAME()<>SUSER_SNAME()", "sid=SUSER_SID()", "THROW 53001"):
                self.assertIn(text, guard)

    def test_mutations_use_transactions_validation_and_safe_rollback(self):
        for name, body in self.bodies.items():
            with self.subTest(procedure=name):
                self.assertIn("SET XACT_ABORT ON", body)
                self.assertIn("@MAGV nvarchar(max)", body)
                self.assertIn("DATALENGTH(@MAGV)<>20", body)
                self.assertIn("UNICODE(LEFT(@MAGV,1))", body)
                self.assertIn("UNICODE(RIGHT(@MAGV,1))", body)
                self.assertLess(body.index("BEGIN TRANSACTION"), body.index("DATALENGTH(@MAGV)"))
                self.assertIn("IF @@TRANCOUNT>0 ROLLBACK TRANSACTION", body)
                self.assertIn("IF @Error BETWEEN 53001 AND 53009 THROW", body)
                self.assertIn("THROW 53008", body)

    def test_add_rejects_duplicate_and_principal_drift_before_insert(self):
        body = self.bodies["sp_ThemGiangVien"]
        for text in ("THROW 53003", "sys.server_principals WHERE name=@MAGV", "sys.database_principals WHERE name=@MAGV", "THROW 53006"):
            self.assertIn(text, body)
            self.assertLess(body.index(text), body.index("INSERT dbo.Giangvien"))
        self.assertIn("HAS_PERMS_BY_NAME(NULL,NULL,N'ALTER ANY LOGIN')", body)

    def test_update_changes_only_name_and_gender_and_checks_missing_entity(self):
        body = self.bodies["sp_CapNhatGiangVien"]
        self.assertRegex(body, r"UPDATE\s+dbo\.Giangvien\s+SET\s+HO=@HO,TEN=@TEN,PHAI=@PHAI\s+WHERE\s+MAGV=@MAGV")
        self.assertNotRegex(body, r"SET\s+MAGV\s*=")
        self.assertIn("THROW 53004", body)
        for name in ("sp_ThemGiangVien", "sp_CapNhatGiangVien"):
            self.assertIn("DATALENGTH(@HO)>80", self.bodies[name])
            self.assertIn("DATALENGTH(@TEN)>20", self.bodies[name])
            self.assertIn("@PHAI bit", self.bodies[name])
            self.assertIn("@PHAI IS NULL", self.bodies[name])

    def test_delete_lock_precedes_principals_assignments_and_delete(self):
        body = self.bodies["sp_XoaGiangVien"]
        lock = re.search(r"FROM\s+dbo\.Giangvien\s+WITH\s*\(UPDLOCK,\s*HOLDLOCK\)\s+WHERE\s+MAGV=@MAGV", body)
        self.assertIsNotNone(lock)
        self.assertLess(body.index("BEGIN TRANSACTION"), lock.start())
        for text in ("sys.server_principals", "sys.database_principals WHERE name=@MAGV", "FROM dbo.PhanCong", "DELETE FROM dbo.Giangvien"):
            # The caller's mapping guard uses metadata too; compare only the transaction body.
            self.assertLess(lock.start(), body.index(text, body.index("BEGIN TRANSACTION")))
        self.assertIn("dbo.PhanCong WITH (UPDLOCK,HOLDLOCK)", body)
        self.assertIn("THROW 53006", body)
        self.assertIn("THROW 53007", body)
        self.assertLess(body.index("DELETE FROM dbo.Giangvien"), body.index("COMMIT TRANSACTION"))
        security = (ROOT / "database/StoredProcedures_Security.sql").read_text(encoding="utf-8")
        self.assertRegex(security, r"dbo\.Giangvien\s+WITH\s*\(UPDLOCK,\s*HOLDLOCK\)")
        self.assertNotIn("ON DELETE CASCADE", (ROOT / "database/CreatePhanCong.sql").read_text(encoding="utf-8"))

    def test_permissions_grant_admin_and_deny_nonadmins_for_all_four_procedures(self):
        for name in ("sp_GetGiangVien", *self.bodies):
            self.assertIn(f"GRANT EXECUTE ON OBJECT::dbo.{name} TO QLDSV_ADMIN;", self.sql)
            for role in ("GIANGVIEN", "SINHVIEN"):
                self.assertIn(f"DENY EXECUTE ON OBJECT::dbo.{name} TO QLDSV_{role};", self.sql)
        self.assertNotIn("ON SCHEMA::", self.sql)

    def test_business_sql_has_no_account_or_assignment_mutation(self):
        for forbidden in ("dbo.TaiKhoan", "CREATE LOGIN", "DROP LOGIN", "CREATE USER", "DROP USER", "DELETE dbo.PhanCong", "DELETE FROM dbo.PhanCong"):
            self.assertNotIn(forbidden, self.sql)
        self.assertNotRegex(self.sql, r"\bEXEC(?:UTE)?\s+(?:dbo\.)?sp_(?:Tao|Xoa)TaiKhoan\b")
        self.assertNotRegex(self.sql, r"EXEC(?:UTE)?\s*\(")

    def test_bootstrap_installs_after_common_seed_and_security_roles(self):
        source = (ROOT / "docker/init-db.sh").read_text(encoding="utf-8")
        block = source[source.index('run_sql_file "storedProcedure.sql"'):]
        module = block.index('run_sql_file "StoredProcedures_Lecturer.sql"')
        for previous in ('run_sql_file "seedData.sql"', "run_security", 'run_optional_sql_file "StoredProcedures_Security.sql"'):
            self.assertLess(block.index(previous), module)
        self.assertIn("THROW 53009", self.sql[:self.sql.index("CREATE PROCEDURE")])

    def test_future_verifier_preserves_account_sid_and_only_disposable_assignment(self):
        source = (ROOT / "docker/verify-lecturer-management.py").read_text(encoding="utf-8")
        self.assertIn("@CreatedSid=@CreatedSid OUTPUT", source)
        self.assertIn("@ExpectedSid=?", source)
        self.assertIn("WHERE MAGV=? AND MALOP=? AND MAMH=?", source)
        self.assertIn("preflight(control, magv)", source)
        self.assertLess(source.index("pair = preflight"), source.index("service.create_lecturer"))
        self.assertIn("finally:", source)
        for forbidden in ("-U sa", "KILL ", "RESTORE DATABASE", "docker compose"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
