"""Epic 1.8 real-principal verifier. No Docker, deployment or credential reset.

Default: create/list/verify one owned backup, then safely remove that file.
ONLY QLDSV_ALLOW_LIVE_RESTORE=YES enables the QLDSV restore acceptance.
Restoring QLDSV discards all changes made after the backup, including other users'.
"""

import getpass
import os
from pathlib import Path
import re
import secrets
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.database import open_sql_connection
from app.services.auth_service import AuthService
from app.services.backup_restore_service import BackupRestoreService
from app.utils import session


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def query(connection, sql, *parameters):
    cursor = connection.cursor()
    try:
        cursor.execute(sql, *parameters)
        rows = []
        while True:
            if cursor.description is not None:
                rows = cursor.fetchall()
            if not cursor.nextset():
                return rows
    finally:
        parameters = ()
        cursor.close()


def fingerprint(path):
    check(not path.is_symlink() and path.is_file(), "Owned backup disappeared or became a symlink")
    info = path.stat()
    check(info.st_ino != 0, "Filesystem supplies no backup identity; retain the file for manual cleanup")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def cleanup_backup(path, original, host):
    check(path.parent.resolve() == host and fingerprint(path) == original,
          "Backup file identity changed; no cleanup by guessed filename")
    path.unlink()
    print("PASS owned backup file removed: " + path.name)


def check_core_database():
    rows = query(session.require_qldsv_connection(), """
SELECT DB_NAME(), @@TRANCOUNT,
       (SELECT user_access_desc FROM sys.databases WHERE database_id=DB_ID()),
       (SELECT COUNT(*) FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
        WHERE s.name=N'dbo' AND t.name IN(N'Lop',N'Sinhvien',N'Giangvien',N'Monhoc',N'Diem')),
       CONVERT(int,SERVERPROPERTY('ProductMajorVersion')),
       (SELECT compatibility_level FROM sys.databases WHERE database_id=DB_ID());
""")
    check(len(rows) == 1 and tuple(rows[0]) == ("QLDSV", 0, "MULTI_USER", 5, 16, 160),
          "Require QLDSV MULTI_USER, five core tables, SQL Server 2022 and existing compatibility 160")


def preflight(service, admin):
    check_core_database()
    row = query(session.require_master_connection(), """
SELECT SUSER_SNAME(), ORIGINAL_LOGIN(), DB_NAME(), IS_SRVROLEMEMBER(N'dbcreator'),
       IS_SRVROLEMEMBER(N'sysadmin'), IS_SRVROLEMEMBER(N'securityadmin'),
       HAS_PERMS_BY_NAME(NULL,NULL,N'CONTROL SERVER');
""")[0]
    check(tuple(row) == (admin, admin, "master", 1, 0, 0, 0), "Require the same application Admin on master with only the existing delegated privileges")
    row = query(session.require_qldsv_connection(), """
SELECT HAS_PERMS_BY_NAME(DB_NAME(),N'DATABASE',N'BACKUP DATABASE'),
       HAS_PERMS_BY_NAME(DB_NAME(),N'DATABASE',N'CONTROL');
""")[0]
    check(tuple(row) == (1, 1), "Application Admin lacks QLDSV backup/control permission; do not substitute another principal")
    host = service._directory()
    service._sql_path("Epic18_mapping_check.bak")  # Validate only; never stat the Linux path.
    return host


def audit_nonadmin_permissions():
    # Read-only Admin metadata audit. No impersonation or permission changes.
    rows = query(session.require_qldsv_connection(), """
SELECT COUNT(*) FROM sys.database_permissions p
JOIN sys.database_principals u ON u.principal_id=p.grantee_principal_id
WHERE p.state IN('G','W') AND p.class=0
 AND p.permission_name IN(N'BACKUP DATABASE',N'BACKUP LOG',N'CONTROL',N'ALTER')
 AND (u.name IN(N'QLDSV_SINHVIEN',N'QLDSV_GIANGVIEN')
      OR IS_ROLEMEMBER(N'QLDSV_SINHVIEN',u.name)=1 OR IS_ROLEMEMBER(N'QLDSV_GIANGVIEN',u.name)=1);
""")
    check(rows[0][0] == 0, "Unexpected non-Admin database backup/control grants")
    rows = query(session.require_qldsv_connection(), """
SELECT COUNT(*) FROM sys.database_principals u
JOIN sys.server_principals sp ON sp.name=u.name AND sp.sid=u.sid
WHERE (IS_ROLEMEMBER(N'QLDSV_SINHVIEN',u.name)=1 OR IS_ROLEMEMBER(N'QLDSV_GIANGVIEN',u.name)=1)
 AND (EXISTS(SELECT 1 FROM sys.server_role_members WHERE member_principal_id=sp.principal_id)
 OR EXISTS(SELECT 1 FROM sys.server_permissions WHERE grantee_principal_id=sp.principal_id
           AND state IN('G','W') AND permission_name NOT IN(N'CONNECT SQL',N'VIEW ANY DATABASE')));
""")
    check(rows[0][0] == 0, "Unexpected non-Admin server role/grants")
    print("PASS read-only non-Admin privilege metadata audit")
    for prefix, expected in (("STUDENT", "QLDSV_SINHVIEN"), ("LECTURER", "QLDSV_GIANGVIEN")):
        name = os.getenv("QLDSV_VERIFY_" + prefix + "_LOGIN")
        password = os.getenv("QLDSV_VERIFY_" + prefix + "_PASSWORD")
        connection = None
        try:
            if not name or not password:
                print("SKIP real " + prefix + " permission query: optional current credential unavailable; metadata audit only")
                continue
            check(len(name.encode("utf-16-le")) == 20, "Non-Admin must be a mapped business identity")
            connection = open_sql_connection(name, password)  # QLDSV only; never publish a master session.
            password = ""
            identity = query(connection, "EXEC dbo.sp_ThongTinDangNhap;")
            check(len(identity) == 1 and tuple(identity[0]) == (name, name, expected), "Non-Admin identity mismatch")
            row = query(connection, """
SELECT HAS_PERMS_BY_NAME(DB_NAME(),N'DATABASE',N'BACKUP DATABASE'),
       HAS_PERMS_BY_NAME(DB_NAME(),N'DATABASE',N'BACKUP LOG'),
       HAS_PERMS_BY_NAME(DB_NAME(),N'DATABASE',N'CONTROL'),
       IS_SRVROLEMEMBER(N'dbcreator'), IS_SRVROLEMEMBER(N'sysadmin');
""")[0]
            check(tuple(row) == (0, 0, 0, 0, 0), "Non-Admin unexpectedly has backup/restore capabilities")
            print("PASS real " + prefix + " read-only backup/restore permission denial")
        finally:
            password = ""
            session.close_connection(connection)


def cleanup_probe(name, expected_id, token):
    check(re.fullmatch(r"Epic18Probe_[0-9a-f]{24}", name), "Invalid verifier probe identifier")
    query(session.require_qldsv_connection(), f"""
IF OBJECT_ID(?,N'U') IS NOT NULL
BEGIN
    IF OBJECT_ID(?,N'U')<>? OR (SELECT COUNT(*) FROM dbo.[{name}])<>1
       OR NOT EXISTS(SELECT 1 FROM dbo.[{name}] WHERE Token=CONVERT(uniqueidentifier,?))
        THROW 53121, 'Verifier probe identity changed; cleanup refused.', 1;
    DROP TABLE dbo.[{name}];
END;
""", "dbo." + name, "dbo." + name, expected_id, token)


def restore_acceptance(service, item, admin, password):
    # Gate inside this function too, so direct callers cannot bypass the opt-in.
    check(os.getenv("QLDSV_ALLOW_LIVE_RESTORE") == "YES", "Destructive QLDSV restore requires exact QLDSV_ALLOW_LIVE_RESTORE=YES")
    name = "Epic18Probe_" + secrets.token_hex(12)
    token = str(uuid.uuid4())
    expected_id = None
    uncertain = False
    try:
        check_core_database()
        service.verify_backup(item.filename, item.position)
        row = query(session.require_qldsv_connection(), """
SELECT HAS_PERMS_BY_NAME(DB_NAME(),N'DATABASE',N'CREATE TABLE'),
       HAS_PERMS_BY_NAME(N'dbo',N'SCHEMA',N'ALTER');
""")[0]
        check(tuple(row) == (1, 1), "Probe prerequisites missing; no destructive mutation performed")
        uncertain = True
        rows = query(session.require_qldsv_connection(), f"""
SET NOCOUNT ON; SET XACT_ABORT ON;
BEGIN TRY
    BEGIN TRANSACTION;
    IF OBJECT_ID(?) IS NOT NULL THROW 53120, 'Verifier probe already exists; refuse reuse.', 1;
    CREATE TABLE dbo.[{name}](Token uniqueidentifier NOT NULL);
    INSERT dbo.[{name}](Token) VALUES(CONVERT(uniqueidentifier,?));
    SELECT OBJECT_ID(?,N'U');
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
""", "dbo." + name, token, "dbo." + name)
        check(len(rows) == 1 and type(rows[0][0]) is int, "Probe creation ownership is uncertain")
        expected_id, uncertain = rows[0][0], False
        row = query(session.require_qldsv_connection(), f"SELECT Token FROM dbo.[{name}];")[0]
        check(str(row[0]).lower() == token, "Post-backup probe missing")
        print("Probe created after backup: " + name)
        service.restore_database(item.filename, item.position)
        check(session.current_user is None, "Restore failed to invalidate the application session")
        # Explicit acceptance-test reauthentication, never an application reconnect.
        AuthService().login(admin, password)
        password = ""
        row = query(session.require_qldsv_connection(), "SELECT OBJECT_ID(?,N'U');", "dbo." + name)[0]
        check(row[0] is None, "Post-backup probe survived restore")
        expected_id = None
        check_core_database()
        print("PASS destructive acceptance: backup -> owned probe -> exact FILE restore -> probe absent; MULTI_USER and core tables intact")
    finally:
        password = ""
        if uncertain:
            print("Probe creation ownership uncertain: " + name + "; inspect manually, never delete by guessed name", file=sys.stderr)
        if expected_id is not None:
            try:
                cleanup_probe(name, expected_id, token)
            except Exception:
                uncertain = True
                print("Probe cleanup incomplete: " + name + "; original object_id=" + str(expected_id), file=sys.stderr)
        if uncertain:
            raise RuntimeError("Verifier probe cleanup is uncertain; manual inspection required") from None


def main():
    admin = os.getenv("QLDSV_ADMIN_LOGIN", "GV00000001")
    check(len(admin.encode("utf-16-le")) == 20, "Application Admin must be an existing MAGV; system principals forbidden")
    password = os.getenv("QLDSV_ADMIN_PASSWORD")
    if not password:
        if not sys.stdin.isatty():
            raise RuntimeError("BLOCKED: current application Admin password unavailable; never guess or reset it")
        password = getpass.getpass("Current application Admin SQL password: ")
    allow_restore = os.getenv("QLDSV_ALLOW_LIVE_RESTORE") == "YES"
    owned = None
    backup_uncertain = False
    restore_succeeded = False
    try:
        user = AuthService().login(admin, password)
        check(user.role == "Admin" and user.username == user.magv == admin, "Require real mapped application Admin")
        service = BackupRestoreService()
        host = preflight(service, admin)
        audit_nonadmin_permissions()
        if allow_restore:
            print("WARNING: opted-in QLDSV restore discards ALL changes made after this backup. Run only on an authorized test database.", flush=True)
        else:
            password = ""
            print("SKIP destructive QLDSV restore: exact QLDSV_ALLOW_LIVE_RESTORE=YES not supplied")
        backup_uncertain = True
        item = service.backup_database()
        check(item.path.parent == host and item.user_name == admin and item.position == 1,
              "Production backup host mapping/creator/position mismatch")
        owned = item.path, fingerprint(item.path), host
        backup_uncertain = False
        listed = service.list_backups()
        check(any(row == item for row in listed), "Production history did not return the exact header metadata")
        service.verify_backup(item.filename, item.position)
        print("PASS real Admin production backup, host visibility, HEADERONLY time/user/position and selected-set VERIFYONLY: " + item.filename)
        if allow_restore:
            check(fingerprint(item.path) == owned[1], "Backup identity changed before restore acceptance; no probe mutation")
            restore_acceptance(service, item, admin, password)
            password = ""
            restore_succeeded = True
    finally:
        password = ""
        session.clear_session()
        if backup_uncertain:
            print("Backup creation/ownership uncertain; inspect shared folder manually. No guessed file deletion.", file=sys.stderr)
        if owned is not None:
            if allow_restore and not restore_succeeded:
                print("Restore acceptance failed; retain recovery backup for manual inspection: " + str(owned[0]), file=sys.stderr)
            else:
                try:
                    cleanup_backup(*owned)
                except Exception:
                    print("Owned backup cleanup incomplete; retained: " + str(owned[0]), file=sys.stderr)
                    raise RuntimeError("Backup cleanup uncertain; no delete-by-name fallback") from None


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("FAIL/BLOCKED Epic 1.8: inspect current Admin credential, DB_* target, shared-folder mapping, permissions and any cleanup messages. No credential reset or privilege escalation was attempted.", file=sys.stderr)
        raise SystemExit(1) from None
