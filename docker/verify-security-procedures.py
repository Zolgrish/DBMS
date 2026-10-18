"""Real-principal Epic 1.4 tests; run after Docker db-init.

python docker/verify-security-procedures.py
Current bootstrap Admin password: QLDSV_ADMIN_PASSWORD or a hidden prompt.
Reuses Epic 1.3's SQLCMD transport; never imports application auth code.
Requires unused seed principal SV00000002; existing business rows are untouched.
Drift/locking tests insert and finally remove uniquely named disposable Students.
All temporary passwords are in memory/stdin/environment, never command argv.
"""

from contextlib import contextmanager
import getpass
import importlib.util
import os
from pathlib import Path
import queue
import secrets
import subprocess
import threading


spec = importlib.util.spec_from_file_location("security_base", Path(__file__).with_name("verify-security.py"))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
STUDENT = "SV00000002"
PREFIX = "__SEC14_" + secrets.token_hex(8)


def value(text):
    return "NULL" if text is None else "CONVERT(nvarchar(max)," + base.hex_value(text) + ")"


def create_query(name, role, password=None):
    return f"""
DECLARE @n nvarchar(max)={value(name)}, @r nvarchar(max)={value(role)}, @p nvarchar(max)={value(password)};
EXEC dbo.sp_TaoTaiKhoan @LoginName=@n,@Role=@r,@Password=@p;
"""


def delete_query(name):
    return f"DECLARE @n nvarchar(max)={value(name)}; EXEC dbo.sp_XoaTaiKhoan @LoginName=@n;"


def rejected(label, login, password, query, error):
    result = base.sql(login, password, query, expect_success=False)
    diagnostic = (result.stdout + result.stderr).lower()
    if result.returncode == 0 or not (f"msg {error}" in diagnostic or f"hresult 0x{error:X}".lower() in diagnostic):
        # Never expose raw SQL containing credentials in an exception.
        raise RuntimeError(f"Expected rejection {error} did not occur: {label}")
    print(f"PASS rejected: {label} ({error})", flush=True)


def absent(*names):
    for name in names:
        base.sql("sa", None, f"""
IF EXISTS(SELECT 1 FROM sys.server_principals WHERE name={base.literal(name)})
 OR EXISTS(SELECT 1 FROM sys.database_principals WHERE name={base.literal(name)})
    THROW 52100, 'Orphan/unexpected test principal remains.', 1;
""", sa=True)


def identity(login, password, role):
    base.sql(login, password, base.checked(f"""
DECLARE @i TABLE(LoginName sysname,DatabaseUser sysname,RoleName sysname);
INSERT @i EXEC dbo.sp_ThongTinDangNhap;
IF (SELECT COUNT(*) FROM @i)<>1 OR EXISTS(SELECT 1 FROM @i
 WHERE LoginName<>{base.literal(login)} OR DatabaseUser<>{base.literal(login)} OR RoleName<>{base.literal(role)})
    THROW 52101, 'Identity procedure result mismatch.', 1;
""", role, login))


def admin_capabilities(login, password):
    base.sql(login, password, base.checked("""
IF ISNULL(IS_SRVROLEMEMBER(N'QLDSV_ACCOUNT_ADMIN'),-1)<>1
 OR ISNULL(IS_SRVROLEMEMBER(N'dbcreator'),-1)<>1
 OR ISNULL(HAS_PERMS_BY_NAME(NULL,NULL,'ALTER ANY LOGIN'),0)<>1
 OR ISNULL(HAS_PERMS_BY_NAME(N'QLDSV_ACCOUNT_ADMIN','SERVER ROLE','ALTER'),0)<>1
 OR ISNULL(HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONTROL'),0)<>1
 OR ISNULL(HAS_PERMS_BY_NAME(NULL,NULL,'CONTROL SERVER'),-1)<>0
 OR ISNULL(HAS_PERMS_BY_NAME(NULL,NULL,'ALTER ANY SERVER ROLE'),-1)<>0
    THROW 52102, 'Delegated Admin capability mismatch.', 1;
""", "QLDSV_ADMIN", login))
    identity(login, password, "QLDSV_ADMIN")


def session_batch(process, query, expected=None):
    process.stdin.write("SET NOCOUNT ON;\n" + query + "\nGO\n")
    process.stdin.flush()
    ready = queue.Queue()
    def read_result():
        # SQLCMD can emit blank separator lines after a caught SQL error.
        for line in process.stdout:
            if line.strip():
                ready.put(line)
                return
        ready.put("")
    threading.Thread(target=read_result, daemon=True).start()
    result = ready.get(timeout=15).strip()
    if not result or (expected is not None and result != expected):
        raise RuntimeError("Disposable SQL session returned an unexpected result")
    return result


@contextmanager
def held_connection(login, password, setup_sql=""):
    env = os.environ.copy()
    env["SQLCMDPASSWORD"] = password
    process = subprocess.Popen([
        "docker", "exec", "-i", "-e", "SQLCMDPASSWORD", base.CONTAINER, base.SQLCMD,
        "-S", "localhost", "-U", login, "-C", "-b", "-r1", "-d", "QLDSV", "-h", "-1", "-W",
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        session_batch(process, setup_sql + "\nSELECT N'SEC14_READY';", "SEC14_READY")
        yield process
    finally:
        if process.poll() is None:
            try:
                process.stdin.write("IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;\nGO\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
        try:
            process.stdin.close()  # EOF closes only our own SQLCMD connection.
        except (BrokenPipeError, OSError):
            pass
        try:
            process.wait(timeout=15)
        finally:
            process.stdout.close()
            process.stderr.close()


@contextmanager
def disposable_student_row(admin, password):
    masv = "Z" + secrets.token_hex(5)[:9].upper()  # Exactly 10 characters.
    absent(masv)
    base.sql(admin, password, f"""
IF EXISTS(SELECT 1 FROM dbo.Sinhvien WHERE MASV={base.literal(masv)})
    THROW 52110, 'Disposable MASV collision; existing row was not changed.', 1;
INSERT dbo.Sinhvien(MASV,MALOP,PHAI,NGHIHOC)
SELECT TOP (1) {base.literal(masv)},MALOP,1,0 FROM dbo.Lop ORDER BY MALOP;
IF @@ROWCOUNT<>1 THROW 52110, 'A valid existing class is required for the disposable Student.', 1;
""")
    try:
        yield masv
    finally:
        base.sql(admin, password, f"""
IF DATABASE_PRINCIPAL_ID({base.literal(masv)}) IS NOT NULL DROP USER {base.identifier(masv)};
IF SUSER_ID({base.literal(masv)}) IS NOT NULL DROP LOGIN {base.identifier(masv)};
DELETE dbo.Sinhvien WHERE MASV={base.literal(masv)};
IF EXISTS(SELECT 1 FROM dbo.Sinhvien WHERE MASV={base.literal(masv)})
    THROW 52110, 'Disposable Student row cleanup failed.', 1;
""")
        absent(masv)


def security_preflight(expected_error=None):
    # Security.sql alone: expected rejection must not recreate common SPs.
    env = os.environ.copy()
    env.update(QLDSV_ADMIN_LOGIN_HEX=base.hex_value(base.ADMIN), QLDSV_ADMIN_PASSWORD_HEX="0x",
               QLDSV_STUDENT_LOGIN_HEX=base.hex_value(base.STUDENT))
    result = base.run([
        "docker", "compose", "run", "--rm", "--no-deps",
        "-e", "QLDSV_ADMIN_LOGIN_HEX", "-e", "QLDSV_ADMIN_PASSWORD_HEX",
        "-e", "QLDSV_STUDENT_LOGIN_HEX", "--entrypoint", "/bin/bash", "db-init", "-c",
        'export SQLCMDPASSWORD="$MSSQL_SA_PASSWORD"; exec ' + base.SQLCMD
        + ' -S "$DB_HOST,$DB_PORT" -U sa -C -b -r1 -i /opt/qldsv/database/Security.sql',
    ], env=env)
    if expected_error is None:
        if result.returncode:
            raise RuntimeError("Security.sql rejected legitimate delegated Admin membership")
    elif result.returncode == 0 or f"Msg {expected_error}" not in result.stdout + result.stderr:
        raise RuntimeError("Security.sql did not reject technical-role member drift with the expected error")


def technical_role_drift(admin, password):
    security_preflight()  # Existing bootstrap and delegated Admins are valid.
    with disposable_student_row(admin, password) as masv:
        base.sql(admin, password, create_query(masv, "QLDSV_SINHVIEN"))
        try:
            base.sql(admin, password, f"ALTER SERVER ROLE QLDSV_ACCOUNT_ADMIN ADD MEMBER {base.identifier(masv)};")
            security_preflight(51007)
            base.sql("sa", None, f"""
IF NOT EXISTS(SELECT 1 FROM sys.server_role_members WHERE role_principal_id=SUSER_ID(N'QLDSV_ACCOUNT_ADMIN')
              AND member_principal_id=SUSER_ID({base.literal(masv)}))
    THROW 52111, 'Preflight silently removed Student drift instead of reporting it.', 1;
""", sa=True)
        finally:
            base.sql(admin, password, f"""
IF EXISTS(SELECT 1 FROM sys.server_role_members WHERE role_principal_id=SUSER_ID(N'QLDSV_ACCOUNT_ADMIN')
          AND member_principal_id=SUSER_ID({base.literal(masv)}))
    ALTER SERVER ROLE QLDSV_ACCOUNT_ADMIN DROP MEMBER {base.identifier(masv)};
""")
        base.sql(admin, password, delete_query(masv))
        absent(masv)
    unmapped = PREFIX + "_unmapped"
    absent(unmapped)
    try:
        base.sql(admin, password, f"CREATE LOGIN {base.identifier(unmapped)} WITH PASSWORD={base.literal('Drift#'+secrets.token_hex(20)+'!')},CHECK_POLICY=ON;")
        base.sql(admin, password, f"ALTER SERVER ROLE QLDSV_ACCOUNT_ADMIN ADD MEMBER {base.identifier(unmapped)};")
        security_preflight(51007)
        base.sql("sa", None, f"""
IF DATABASE_PRINCIPAL_ID({base.literal(unmapped)}) IS NOT NULL
 OR NOT EXISTS(SELECT 1 FROM sys.server_role_members WHERE role_principal_id=SUSER_ID(N'QLDSV_ACCOUNT_ADMIN')
               AND member_principal_id=SUSER_ID({base.literal(unmapped)}))
    THROW 52111, 'Preflight silently remapped/removed an unmanaged Login.', 1;
""", sa=True)
    finally:
        base.sql(admin, password, f"""
IF EXISTS(SELECT 1 FROM sys.server_role_members WHERE role_principal_id=SUSER_ID(N'QLDSV_ACCOUNT_ADMIN')
          AND member_principal_id=SUSER_ID({base.literal(unmapped)}))
    ALTER SERVER ROLE QLDSV_ACCOUNT_ADMIN DROP MEMBER {base.identifier(unmapped)};
IF SUSER_ID({base.literal(unmapped)}) IS NOT NULL DROP LOGIN {base.identifier(unmapped)};
""")
    absent(unmapped)
    security_preflight()
    admin_capabilities(admin, password)
    print("PASS technical-role drift: Student/unmapped members rejected (51007), not auto-repaired; legitimate delegated Admin accepted", flush=True)


def disabled_delete(admin, password):
    name = PREFIX + "_disabled"
    absent(name)
    try:
        base.sql(admin, password, create_query(name, "QLDSV_ADMIN", "Disabled#"+secrets.token_hex(20)+"!"))
        ids = base.sql("sa", None, f"SET NOCOUNT ON; SELECT SUSER_ID({base.literal(name)}),DATABASE_PRINCIPAL_ID({base.literal(name)});", sa=True)
        login_id, user_id = map(int, ids.stdout.split())
        base.sql(admin, password, f"ALTER LOGIN {base.identifier(name)} DISABLE;")
        base.sql("sa", None, f"IF NOT EXISTS(SELECT 1 FROM sys.sql_logins WHERE name={base.literal(name)} AND is_disabled=1) THROW 52112,'Disposable Login was not disabled.',1;", sa=True)
        base.sql(admin, password, delete_query(name))
        absent(name)
        base.sql("sa", None, f"""
IF EXISTS(SELECT 1 FROM sys.server_role_members WHERE member_principal_id={login_id})
 OR EXISTS(SELECT 1 FROM sys.database_role_members WHERE member_principal_id={user_id})
    THROW 52112, 'Disabled account deletion left orphan role memberships.', 1;
""", sa=True)
    finally:
        base.sql(admin, password, f"IF DATABASE_PRINCIPAL_ID({base.literal(name)}) IS NOT NULL DROP USER {base.identifier(name)}; IF SUSER_ID({base.literal(name)}) IS NOT NULL DROP LOGIN {base.identifier(name)};")
    absent(name)
    print("PASS disabled managed Admin deletion: Login/User/business+technical/dbcreator memberships removed", flush=True)


def student_creation_lock(admin, password):
    # Both real Admin connections exist before principal DDL takes catalog
    # locks. No polling, WAITFOR, application locks or existing Student changes.
    with disposable_student_row(admin, password) as masv:
        hobt = int(base.sql("sa", None, "SET NOCOUNT ON; SELECT hobt_id FROM sys.partitions WHERE object_id=OBJECT_ID(N'dbo.Sinhvien') AND index_id=1;", sa=True).stdout.strip())
        with held_connection(admin, password, "SET LOCK_TIMEOUT 1000;") as session_b:
            with held_connection(admin, password, "BEGIN TRANSACTION;\n" + create_query(masv, "QLDSV_SINHVIEN")
                                 + "IF @@TRANCOUNT<>1 THROW 52113,'Outer creation transaction was not preserved.',1;") as session_a:
                spid, login_id, user_id = map(int, session_batch(session_a, f"""
SELECT CONVERT(nvarchar(12),@@SPID)+N' '+CONVERT(nvarchar(12),SUSER_ID({base.literal(masv)}))
       +N' '+CONVERT(nvarchar(12),DATABASE_PRINCIPAL_ID({base.literal(masv)}));
""").split())
                # SA only observes our session's held entity lock. All account
                # creation and competing DELETE operations use real Admins.
                base.sql("sa", None, f"""
IF NOT EXISTS(SELECT 1 FROM sys.dm_tran_locks WHERE request_session_id={spid}
               AND resource_associated_entity_id={hobt} AND resource_type IN(N'KEY',N'RID',N'PAGE')
               AND request_status=N'GRANT' AND request_mode IN(N'U',N'X',N'RangeS-U',N'RangeX-X'))
    THROW 52113, 'Creation did not retain a Sinhvien update/key lock in its outer transaction.', 1;
""", sa=True)
                # Assert SQLCMD's native error/exit path. Permission-cache or
                # compilation waits can time out before a TRY/CATCH marker.
                session_b.stdin.write(f"""
SET XACT_ABORT ON;
BEGIN TRANSACTION;
EXEC sys.sp_executesql N'DELETE dbo.Sinhvien WHERE MASV=@MASV;',
     N'@MASV nchar(10)', @MASV={base.literal(masv)};
ROLLBACK TRANSACTION; -- Preserve the fixture if locking regresses.
THROW 52113,'Concurrent entity DELETE unexpectedly succeeded.',1;
GO
""")
                session_b.stdin.flush()
                session_b.wait(timeout=10)
                diagnostic = (session_b.stdout.read() + session_b.stderr.read()).lower()
                if session_b.returncode == 0 or not ("msg 1222" in diagnostic or "hresult 0x4c6" in diagnostic):
                    raise RuntimeError("Concurrent Student DELETE did not fail with lock timeout 1222")
            # held_connection explicitly rolled back Session A before closing.
        absent(masv)
        base.sql("sa", None, f"""
IF EXISTS(SELECT 1 FROM sys.server_role_members WHERE member_principal_id={login_id})
 OR EXISTS(SELECT 1 FROM sys.database_role_members WHERE member_principal_id={user_id})
    THROW 52113, 'Outer rollback left orphan role memberships.', 1;
""", sa=True)
        base.sql(admin, password, f"IF NOT EXISTS(SELECT 1 FROM dbo.Sinhvien WHERE MASV={base.literal(masv)}) THROW 52113,'Entity was deleted during creation.',1;")
    print("PASS concurrency: held Sinhvien update/key lock, second Admin DELETE timed out (1222), outer rollback removed principals, disposable row cleaned", flush=True)


def student_checks(admin, admin_password):
    identity(STUDENT, "123456", "QLDSV_SINHVIEN")
    base.sql(STUDENT, "123456", """
SET NOCOUNT ON;
IF ISNULL(IS_SRVROLEMEMBER(N'QLDSV_ACCOUNT_ADMIN'),-1)<>0
 OR ISNULL(IS_SRVROLEMEMBER(N'dbcreator'),-1)<>0
 OR EXISTS(SELECT 1 FROM sys.server_principals WHERE type='R' AND name<>N'public'
           AND ISNULL(IS_SRVROLEMEMBER(name),-1)<>0)
    THROW 52103, 'Student has a server administration role.', 1;
DECLARE @d TABLE(MAMH nchar(5),TENMH nvarchar(40),LAN smallint,DIEM float);
INSERT @d EXEC dbo.sp_SinhVien_XemDiem;
IF (SELECT COUNT(*) FROM @d)<>3 OR EXISTS(
 SELECT MAMH,LAN,DIEM FROM @d EXCEPT
 SELECT * FROM (VALUES(N'CSDL1',1,4.0),(N'CSDL1',2,7.0),(N'CTDL1',1,2.0)) e(MAMH,LAN,DIEM))
    THROW 52103, 'Raw attempts differ from the expected SV00000002 data.', 1;
""")
    rejected("Student direct Diem SELECT", STUDENT, "123456", "SELECT * FROM dbo.Diem;", 229)
    rejected("Student account creation", STUDENT, "123456", create_query(PREFIX+"_forbidden", "QLDSV_ADMIN", "Unused#123456!"), 229)
    rejected("Student account deletion", STUDENT, "123456", delete_query(admin), 229)
    rejected("Student supplies another MASV", STUDENT, "123456", "EXEC dbo.sp_SinhVien_XemDiem @MASV=N'SV00000001';", 8146)
    rejected("Student supplies another Login identity", STUDENT, "123456", "EXEC dbo.sp_ThongTinDangNhap @LoginName=N'SV00000001';", 8146)
    rejected("Admin invokes Student-only query", admin, admin_password, "EXEC dbo.sp_SinhVien_XemDiem;", 52022)
    base.sql("sa", None, """
IF NOT EXISTS(SELECT 1 FROM sys.sql_logins WHERE name=N'SV00000002' AND is_policy_checked=0 AND is_expiration_checked=0)
    THROW 52103, 'Student default-password policy mismatch.', 1;
""", sa=True)
    print("PASS Student: SQL identity, default password, three exact raw attempts, same-owner chain across dbo SELECT DENY", flush=True)


def active_delete(admin, password, child, child_password):
    base.sql(admin, password, create_query(child, "QLDSV_ADMIN", child_password))
    with held_connection(child, child_password):
        rejected("delete of actively connected Admin", admin, password, delete_query(child), 52015)
        base.sql("sa", None, f"""
DECLARE @u int=DATABASE_PRINCIPAL_ID({base.literal(child)}), @l int=SUSER_ID({base.literal(child)});
IF @u IS NULL OR @l IS NULL
 OR NOT EXISTS(SELECT 1 FROM sys.database_principals WHERE principal_id=@u AND sid=SUSER_SID({base.literal(child)}))
 OR NOT EXISTS(SELECT 1 FROM sys.database_role_members WHERE member_principal_id=@u AND role_principal_id=DATABASE_PRINCIPAL_ID(N'QLDSV_ADMIN'))
 OR (SELECT COUNT(*) FROM sys.server_role_members WHERE member_principal_id=@l AND role_principal_id IN(SUSER_ID(N'QLDSV_ACCOUNT_ADMIN'),SUSER_ID(N'dbcreator')))<>2
    THROW 52104, 'Active-session deletion did not fully roll back principal/role changes.', 1;
""", sa=True)
    admin_capabilities(child, child_password)
    base.sql(admin, password, delete_query(child))
    absent(child)
    print("PASS active-session rollback: Login/User/SID/database+server roles intact; deletion succeeds after own client closes", flush=True)


def negative_inputs(admin, password):
    cases = [
        ("invalid business role", PREFIX+"_invalid", "Admin", None, 52003),
        ("arbitrary server role", PREFIX+"_invalid", "sysadmin", None, 52003),
        ("role trailing whitespace", PREFIX+"_invalid", "QLDSV_ADMIN ", None, 52003),
        ("empty LoginName", "", "QLDSV_ADMIN", None, 52002),
        ("NULL LoginName", None, "QLDSV_ADMIN", None, 52002),
        ("oversized LoginName", "x"*129, "QLDSV_ADMIN", None, 52002),
        ("surrounding whitespace", PREFIX+"_space ", "QLDSV_ADMIN", None, 52002),
        ("reserved principal", "sa", "QLDSV_ADMIN", None, 52002),
        ("missing Student MASV", "ZZ99999999", "QLDSV_SINHVIEN", None, 52007),
        ("Student password override", STUDENT, "QLDSV_SINHVIEN", "Conflicting#123!", 52006),
        ("missing Admin password", PREFIX+"_invalid", "QLDSV_ADMIN", None, 52006),
        ("weak Admin password", PREFIX+"_weak", "QLDSV_ADMIN", "123456", 52009),
    ]
    for label, name, role, secret, error in cases:
        rejected(label, admin, password, create_query(name, role, secret), error)
    absent(PREFIX+"_invalid", PREFIX+"_weak", PREFIX+"_space ", "ZZ99999999")
    rejected("self-delete", admin, password, delete_query(admin), 52014)


def main():
    bootstrap_password = os.environ.get("QLDSV_ADMIN_PASSWORD") or getpass.getpass("Current Admin SQL password: ")
    admin = PREFIX+"_admin"
    password = "Admin#"+secrets.token_hex(20)+"!"
    child, failed = PREFIX+"_child", PREFIX+"_rollback"
    orphan, alias, loose = PREFIX+"_orphan", PREFIX+"_alias", PREFIX+"_loose"
    sentinel = PREFIX+"_sentinel"
    injected = PREFIX+"]; DROP TABLE dbo."+sentinel+";--"
    owned_student = False
    # Refuse to touch a pre-existing Student account (including mismatched SID).
    absent(STUDENT, admin, child, failed, orphan, alias, loose, injected)
    base.build_db_init()  # Fresh deployment image, once before test mutations.
    baseline = base.sql("sa", None, "SET NOCOUNT ON; SELECT COUNT(*),CHECKSUM_AGG(BINARY_CHECKSUM(MASV,MAMH,LAN,DIEM)) FROM dbo.Diem;", sa=True).stdout.strip()
    try:
        # Run the procedure file twice under the real Admin, reapplying grants.
        for _ in range(2):
            base.sql(base.ADMIN, bootstrap_password, (base.ROOT/"database"/"StoredProcedures_Security.sql").read_text(encoding="utf-8"))
        print("PASS procedure DROP/CREATE rerun twice as Admin", flush=True)
        base.sql(base.ADMIN, bootstrap_password, create_query(admin, "QLDSV_ADMIN", password))
        admin_capabilities(admin, password)
        print("PASS delegated Admin: CONTROL DATABASE, technical role/self-ALTER, ALTER ANY LOGIN, dbcreator; no global server control", flush=True)
        technical_role_drift(admin, password)
        disabled_delete(admin, password)
        student_creation_lock(admin, password)
        owned_student = True  # Also clean up an unexpected partial creation.
        base.sql(admin, password, create_query(STUDENT, "QLDSV_SINHVIEN"))
        student_checks(admin, password)
        negative_inputs(admin, password)
        rejected("duplicate Login", admin, password, create_query(STUDENT, "QLDSV_SINHVIEN"), 52004)
        active_delete(admin, password, child, "Child#"+secrets.token_hex(20)+"!")

        # Force an ordinary failure AFTER CREATE LOGIN/USER/database membership
        # and technical-role membership. Only our disposable Admin is modified.
        base.sql(base.ADMIN, bootstrap_password, f"ALTER SERVER ROLE dbcreator DROP MEMBER {base.identifier(admin)};")
        try:
            rejected("late CREATE LOGIN transaction failure", admin, password, create_query(failed,"QLDSV_ADMIN","Rollback#"+secrets.token_hex(20)+"!"), 52009)
            absent(failed)
        finally:
            base.sql(base.ADMIN, bootstrap_password, f"ALTER SERVER ROLE dbcreator ADD MEMBER {base.identifier(admin)};")
        print("PASS CREATE LOGIN/USER/server+database memberships roll back atomically on late failure", flush=True)

        base.sql(base.ADMIN, bootstrap_password, f"CREATE USER {base.identifier(orphan)} WITHOUT LOGIN;")
        rejected("duplicate Database User", admin, password, create_query(orphan,"QLDSV_ADMIN",password), 52005)
        base.sql(base.ADMIN, bootstrap_password, f"CREATE LOGIN {base.identifier(loose)} WITH PASSWORD={base.literal(password)},CHECK_POLICY=ON; CREATE USER {base.identifier(alias)} FOR LOGIN {base.identifier(loose)};")
        rejected("existing Login SID with differently named User", admin, password, create_query(loose,"QLDSV_ADMIN",password), 52004)
        rejected("delete mismatched User mapping", admin, password, delete_query(loose), 52011)
        base.sql(base.ADMIN, bootstrap_password, f"DROP USER {base.identifier(alias)}; CREATE USER {base.identifier(loose)} FOR LOGIN {base.identifier(loose)}; GRANT EXECUTE ON OBJECT::dbo.sp_ThongTinDangNhap TO {base.identifier(loose)};")
        rejected("no-role SQL identity", loose, password, "EXEC dbo.sp_ThongTinDangNhap;", 52021)
        base.sql(base.ADMIN, bootstrap_password, f"ALTER ROLE QLDSV_ADMIN ADD MEMBER {base.identifier(loose)}; ALTER ROLE QLDSV_SINHVIEN ADD MEMBER {base.identifier(loose)};")
        rejected("dual-role SQL identity", loose, password, "EXEC dbo.sp_ThongTinDangNhap;", 52021)
        rejected("dual-role account deletion", admin, password, delete_query(loose), 52012)
        rejected("dual-role Student query", loose, password, "EXEC dbo.sp_SinhVien_XemDiem;", 52022)

        # Quoted identifier and password literals must remain data.
        base.sql(base.ADMIN, bootstrap_password, f"CREATE TABLE dbo.{base.identifier(sentinel)}(id int); INSERT dbo.{base.identifier(sentinel)} VALUES(14);")
        special_password = "Quote' ];$(unused)#"+secrets.token_hex(16)+"!"
        base.sql(admin, password, create_query(injected,"QLDSV_ADMIN",special_password))
        admin_capabilities(injected,special_password)
        base.sql(base.ADMIN, bootstrap_password, f"IF (SELECT COUNT(*) FROM dbo.{base.identifier(sentinel)} WHERE id=14)<>1 THROW 52105,'Identifier injection changed the sentinel.',1;")
        base.sql(admin,password,delete_query(injected))
        absent(injected)
        print("PASS identifier/password injection attempts remain quoted data; sentinel unchanged", flush=True)

        # Prove the complete normal bootstrap tolerates the safe grants and
        # delegated Admin while preserving a changed Student password.
        changed = "Student#"+secrets.token_hex(20)+"!"
        base.sql(admin,password,f"ALTER LOGIN {base.identifier(STUDENT)} WITH PASSWORD={base.literal(changed)};")
        result = base.run(["docker","compose","run","--rm","--no-deps","db-init"])
        if result.returncode or "Epic 1.4: security procedures" not in result.stdout:
            raise RuntimeError("Normal db-init failed or did not execute StoredProcedures_Security.sql")
        identity(STUDENT,changed,"QLDSV_SINHVIEN")
        admin_capabilities(admin,password)
        admin_capabilities(base.ADMIN,bootstrap_password)
        if base.sql(STUDENT,"123456","SELECT 1;",expect_success=False).returncode==0:
            raise RuntimeError("db-init reset the changed Student password")
        print("PASS normal Docker hook, object grants reapplied, Admin/changed Student passwords preserved", flush=True)
        base.sql(admin,password,delete_query(STUDENT))
        owned_student=False
        absent(STUDENT)
        base.sql(base.ADMIN,bootstrap_password,delete_query(admin))
        absent(admin)
    finally:
        # Cleanup targets were verified absent at entry; never drop an account
        # belonging to the user. No sessions are killed, no business rows touched.
        targets=[injected,loose,alias,orphan,failed,child,admin]
        if owned_student:
            targets.insert(0,STUDENT)
        for name in targets:
            base.sql(base.ADMIN,bootstrap_password,f"IF DATABASE_PRINCIPAL_ID({base.literal(name)}) IS NOT NULL DROP USER {base.identifier(name)}; IF SUSER_ID({base.literal(name)}) IS NOT NULL DROP LOGIN {base.identifier(name)};")
        base.sql(base.ADMIN,bootstrap_password,f"IF OBJECT_ID({base.literal('dbo.'+sentinel)},N'U') IS NOT NULL DROP TABLE dbo.{base.identifier(sentinel)};")
        absent(*targets)
    after=base.sql("sa",None,"SET NOCOUNT ON; SELECT COUNT(*),CHECKSUM_AGG(BINARY_CHECKSUM(MASV,MAMH,LAN,DIEM)) FROM dbo.Diem;",sa=True).stdout.strip()
    if baseline!=after:
        raise RuntimeError("Business score rows changed")
    print("PASS Epic 1.4: all real-principal tests, cleanup and business-data preservation", flush=True)


if __name__=="__main__":
    main()
