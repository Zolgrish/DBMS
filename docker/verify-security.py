"""Epic 1.3 integration checks against the existing, non-destructive Docker stack.

Run from the repository: python docker/verify-security.py
Set QLDSV_ADMIN_PASSWORD to the CURRENT password, or enter it at the hidden prompt.
Optional: QLDSV_ADMIN_LOGIN, QLDSV_STUDENT_LOGIN, QLDSV_STUDENT_PASSWORD.
Uses real SQL connections; provisioning SA is used only for metadata/bootstrap.
Never logs credentials. Requires Python 3 and Docker CLI, no Python packages.
"""

import getpass
import os
from pathlib import Path
import secrets
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CONTAINER = "qldsv-sqlserver"
SQLCMD = "/opt/mssql-tools18/bin/sqlcmd"
ADMIN = os.environ.get("QLDSV_ADMIN_LOGIN", "GV00000001")
STUDENT = os.environ.get("QLDSV_STUDENT_LOGIN", "SV00000001")


def run(args, *, data=None, env=None):
    return subprocess.run(args, input=data, text=True, encoding="utf-8",
                          capture_output=True, cwd=ROOT, env=env)


def identifier(value):
    return "[" + value.replace("]", "]]") + "]"


def literal(value):
    return "N'" + value.replace("'", "''") + "'"


def hex_value(value):
    return "0x" + value.encode("utf-16le").hex()


def sql(login, password, query, *, sa=False, expect_success=True):
    args = ["docker", "exec", "-i"]
    env = os.environ.copy()
    if sa:
        args += [CONTAINER, "bash", "-c",
                 'export SQLCMDPASSWORD="$MSSQL_SA_PASSWORD"; exec '
                 + SQLCMD + ' -S localhost -U sa -C -b -r1 -d QLDSV -h -1 -W']
    else:
        env["SQLCMDPASSWORD"] = password
        args += ["-e", "SQLCMDPASSWORD", CONTAINER, SQLCMD, "-S", "localhost",
                 "-U", login, "-C", "-b", "-r1", "-d", "QLDSV", "-h", "-1", "-W"]
    result = run(args, data=query, env=env)
    if expect_success and result.returncode:
        # Input may contain a password-changing statement. Do not print SQL or
        # raw driver diagnostics; emit only SQL error numbers for diagnosis.
        import re
        codes = re.findall(r"Msg (\d+)", result.stdout + result.stderr)
        raise RuntimeError("SQL check failed for " + login + "; error codes: " + ",".join(codes))
    return result


def checked(query, role, login):
    return f"""
SET NOCOUNT ON; SET XACT_ABORT ON;
IF ORIGINAL_LOGIN() <> {literal(login)} OR SUSER_SNAME() <> {literal(login)}
   OR USER_NAME() <> {literal(login)}
    THROW 51100, 'Login/database user mapping mismatch.', 1;
IF ISNULL(IS_ROLEMEMBER({literal(role)}), -1) <> 1
    THROW 51100, 'Expected business role missing.', 1;
IF ISNULL(IS_SRVROLEMEMBER(N'sysadmin'), -1) <> 0
 OR ISNULL(IS_SRVROLEMEMBER(N'securityadmin'), -1) <> 0
    THROW 51100, 'Unexpected elevated server role.', 1;
SELECT SUSER_SNAME() AS LoginName, USER_NAME() AS DatabaseUser;
{query}
"""


def verify_student(password):
    attempts = []
    for table in ("Lop", "Sinhvien", "Giangvien", "Monhoc", "Diem", "PhanCong"):
        attempts.append(f"SELECT TOP (0) * FROM dbo.{table};")
    attempts += [
        "INSERT dbo.Lop (MALOP,TENLOP) SELECT N'ZZSEC001',N'Security test' WHERE 1=0;",
        "UPDATE dbo.Diem SET DIEM=0 WHERE 1=0;",
        "DELETE FROM dbo.Diem WHERE 1=0;",
        "EXEC dbo.sp_GetLop;", "EXEC dbo.sp_GetMonHoc;", "EXEC dbo.sp_GetGiangVien;",
        "EXEC dbo.sp_GetSinhVienByLop @MALOP=N'CNTT01';",
        "EXEC dbo.sp_GetSinhVienByMa @MASV=N'SV00000002';",
        "EXEC dbo.sp_CheckMaSV @MASV=N'SV00000002';",
        "EXEC dbo.sp_CheckMaLop @MALOP=N'CNTT01';",
        "EXEC dbo.sp_CheckMaMH @MAMH=N'CSDL1';", "EXEC dbo.sp_GetActiveStudents;",
    ]
    query = """
IF EXISTS (SELECT 1 FROM sys.server_principals WHERE type='R' AND name<>N'public'
           AND ISNULL(IS_SRVROLEMEMBER(name), -1) <> 0)
 OR HAS_PERMS_BY_NAME(NULL, NULL, 'ALTER ANY LOGIN') <> 0
 OR HAS_PERMS_BY_NAME(NULL, NULL, 'CREATE ANY DATABASE') <> 0
 OR HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'BACKUP DATABASE') <> 0
    THROW 51101, 'Student has server administration/backup permissions.', 1;
IF ISNULL(IS_ROLEMEMBER(N'QLDSV_ADMIN'), -1) <> 0
    THROW 51101, 'Student also belongs to Admin role.', 1;
"""
    for attempt in attempts:
        query += f"""
BEGIN TRY
    BEGIN TRANSACTION;
    EXEC ({literal(attempt)});
    ROLLBACK TRANSACTION;
    THROW 51102, 'Expected permission denial did not occur.', 1;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    IF ERROR_NUMBER() <> 229 THROW;
END CATCH;
"""
    result = sql(STUDENT, password, checked(query, "QLDSV_SINHVIEN", STUDENT))
    print(result.stdout.strip())
    print(f"PASS Student: {len(attempts)} actual permission denials; no Admin/server/backup rights")


def verify_admin(password):
    # Entire disposable database object/user test rolls back. Real business
    # DML uses zero rows, so project data and constraints remain unchanged.
    query = """
IF ISNULL(IS_ROLEMEMBER(N'QLDSV_SINHVIEN'), -1) <> 0
 OR ISNULL(IS_SRVROLEMEMBER(N'dbcreator'), -1) <> 1
 OR ISNULL(IS_SRVROLEMEMBER(N'QLDSV_ACCOUNT_ADMIN'), -1) <> 1
 OR ISNULL(HAS_PERMS_BY_NAME(NULL, NULL, 'ALTER ANY LOGIN'), -1) <> 1
 OR ISNULL(HAS_PERMS_BY_NAME(N'QLDSV_ACCOUNT_ADMIN', 'SERVER ROLE', 'ALTER'), -1) <> 1
 OR ISNULL(HAS_PERMS_BY_NAME(NULL, NULL, 'CONTROL SERVER'), -1) <> 0
 OR ISNULL(HAS_PERMS_BY_NAME(NULL, NULL, 'ALTER ANY SERVER ROLE'), -1) <> 0
 OR HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CONTROL') <> 1
 OR HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'BACKUP DATABASE') <> 1
    THROW 51103, 'Admin permission mismatch.', 1;
BEGIN TRY
    BEGIN TRANSACTION;
    SELECT COUNT(*) AS AdminScoreRows FROM dbo.Diem;
    INSERT dbo.Lop (MALOP,TENLOP) SELECT N'ZZSEC001',N'Security test' WHERE 1=0;
    UPDATE dbo.Diem SET DIEM=0 WHERE 1=0;
    DELETE FROM dbo.Diem WHERE 1=0;
    DECLARE @obj sysname = N'__SEC13_' + REPLACE(CONVERT(nvarchar(36),NEWID()),N'-',N'');
    DECLARE @s nvarchar(max) = N'CREATE TABLE dbo.' + QUOTENAME(@obj) + N'(id int);'
        + N'INSERT dbo.' + QUOTENAME(@obj) + N' VALUES (1);'
        + N'UPDATE dbo.' + QUOTENAME(@obj) + N' SET id=2;'
        + N'DELETE dbo.' + QUOTENAME(@obj) + N';';
    EXEC (@s);
    SET @s = N'CREATE USER ' + QUOTENAME(@obj) + N' WITHOUT LOGIN;'
        + N'ALTER ROLE QLDSV_ADMIN ADD MEMBER ' + QUOTENAME(@obj) + N';';
    EXEC (@s);
    ROLLBACK TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
"""
    result = sql(ADMIN, password, checked(query, "QLDSV_ADMIN", ADMIN))
    print(result.stdout.strip())
    # CREATE/ALTER/DROP a unique temporary Login as Admin, never as SA.
    temporary = "__SEC13_" + secrets.token_hex(12)
    test_password = "Temp#" + secrets.token_hex(20) + "!"
    try:
        sql(ADMIN, password, f"""
USE master;
DECLARE @p nvarchar(128)=CONVERT(nvarchar(128),{hex_value(test_password)});
DECLARE @s nvarchar(max)=N'CREATE LOGIN {identifier(temporary)} WITH PASSWORD=N'''
 + REPLACE(@p,N'''',N'''''') + N''', CHECK_POLICY=ON;'; EXEC (@s);
ALTER LOGIN {identifier(temporary)} DISABLE;
ALTER LOGIN {identifier(temporary)} ENABLE;
DROP LOGIN {identifier(temporary)};
""")
    finally:
        sql(ADMIN, password, f"USE master; IF SUSER_ID({literal(temporary)}) IS NOT NULL DROP LOGIN {identifier(temporary)};")
    print("PASS Admin: database CRUD/DDL, user/role management, CREATE/ALTER/DROP LOGIN; dbcreator and BACKUP DATABASE rights")


def metadata_query(admin_role="QLDSV_ADMIN", student_role="QLDSV_SINHVIEN"):
    return f"""
SET NOCOUNT ON;
IF CONVERT(int,SERVERPROPERTY('IsIntegratedSecurityOnly')) <> 0
 OR OBJECT_ID(N'dbo.TaiKhoan',N'U') IS NOT NULL
 OR DATABASE_PRINCIPAL_ID(N'QLDSV_GIANGVIEN') IS NOT NULL
    THROW 51104, 'Authentication mode or legacy principal/table mismatch.', 1;
IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name={literal(ADMIN)} AND is_policy_checked=1)
    THROW 51104, 'Admin SQL Login must have CHECK_POLICY=ON.', 1;
IF EXISTS (SELECT 1 FROM sys.server_role_members rm JOIN sys.server_principals p
           ON p.principal_id=rm.member_principal_id WHERE p.name={literal(STUDENT)})
    THROW 51104, 'Student has a server role.', 1;
IF EXISTS (
    SELECT 1 FROM (VALUES ({literal(ADMIN)}, {literal(admin_role)}),
                         ({literal(STUDENT)}, {literal(student_role)})) AS expected(LoginName, RoleName)
    WHERE NOT EXISTS (
        SELECT 1 FROM sys.server_principals sp
        JOIN sys.database_principals dp ON dp.sid=sp.sid
        JOIN sys.database_role_members rm ON rm.member_principal_id=dp.principal_id
        JOIN sys.database_principals r ON r.principal_id=rm.role_principal_id
        WHERE sp.name=expected.LoginName AND dp.name=expected.LoginName
          AND sp.type='S' AND dp.type='S' AND r.type='R' AND r.name=expected.RoleName))
    THROW 51104, 'Expected Login/User SID mapping or business role membership is missing.', 1;
IF EXISTS (SELECT 1 FROM sys.database_role_members
           WHERE member_principal_id=DATABASE_PRINCIPAL_ID({literal(STUDENT)})
             AND role_principal_id=DATABASE_PRINCIPAL_ID(N'QLDSV_ADMIN'))
    THROW 51104, 'Student must not belong to QLDSV_ADMIN.', 1;
SELECT sp.name,sp.type_desc,dp.name AS DatabaseUser,r.name AS BusinessRole
FROM sys.server_principals sp JOIN sys.database_principals dp ON dp.sid=sp.sid
JOIN sys.database_role_members rm ON rm.member_principal_id=dp.principal_id
JOIN sys.database_principals r ON r.principal_id=rm.role_principal_id
WHERE sp.name IN ({literal(ADMIN)},{literal(STUDENT)});
SELECT p.permission_name,p.state_desc FROM sys.database_permissions p
WHERE p.grantee_principal_id=DATABASE_PRINCIPAL_ID(N'QLDSV_SINHVIEN');
"""


def metadata():
    result = sql("sa", None, metadata_query(), sa=True)
    print(result.stdout.strip())
    print("PASS metadata: Mixed Mode, SID mappings, roles, Student denials; no TaiKhoan or QLDSV_GIANGVIEN")


def verify_backup_restore(password):
    # Restore only to a fresh uniquely named database. QLDSV is never backed
    # up/restored/put into SINGLE_USER by this test.
    source = "__SEC13_" + secrets.token_hex(12)
    restored = source + "_restored"
    backup = "/var/opt/mssql/data/" + source + ".bak"
    try:
        sql(ADMIN, password, f"""
USE master;
CREATE DATABASE {identifier(source)};
EXEC(N'USE {identifier(source)}; CREATE TABLE dbo.Probe (id int); INSERT dbo.Probe VALUES (13);');
BACKUP DATABASE {identifier(source)} TO DISK={literal(backup)} WITH INIT;
RESTORE VERIFYONLY FROM DISK={literal(backup)};
RESTORE DATABASE {identifier(restored)} FROM DISK={literal(backup)}
 WITH MOVE {literal(source)} TO {literal('/var/opt/mssql/data/' + restored + '.mdf')},
      MOVE {literal(source + '_log')} TO {literal('/var/opt/mssql/data/' + restored + '_log.ldf')};
EXEC(N'USE {identifier(restored)}; IF (SELECT COUNT(*) FROM dbo.Probe WHERE id=13)<>1
 THROW 51105, ''Disposable restore data mismatch.'', 1;');
""")
    finally:
        sql(ADMIN, password, f"""
USE master;
IF DB_ID({literal(restored)}) IS NOT NULL DROP DATABASE {identifier(restored)};
IF DB_ID({literal(source)}) IS NOT NULL DROP DATABASE {identifier(source)};
""")
        removed = run(["docker", "exec", CONTAINER, "rm", "-f", "--", backup])
        if removed.returncode:
            raise RuntimeError("Could not remove the disposable backup file: " + backup)
    print("PASS Admin: CREATE DATABASE, actual BACKUP/VERIFYONLY/RESTORE of disposable data, DROP DATABASE; cleanup complete")


def verify_conflict_guards():
    # Faults use unique disposable principals inside an outer transaction.
    # A rejected Security.sql rolls back that whole transaction; connection
    # closure is also a rollback safeguard if a preflight fails before TRY.
    bootstrap = (ROOT / "database" / "Security.sql").read_text(encoding="utf-8")
    temporary = "__SEC13_" + secrets.token_hex(12)
    other = temporary + "_other"
    password = "Collision#" + secrets.token_hex(20) + "!"
    create_logins = ""
    for name in (temporary, other):
        create_logins += (f"EXEC(N'CREATE LOGIN {identifier(name)} WITH PASSWORD="
                          f"N''{password}'', CHECK_POLICY=ON;');\n")
    scenarios = [
        ("server principal type", f"USE master; BEGIN TRANSACTION; CREATE SERVER ROLE {identifier(temporary)} AUTHORIZATION sa;\n", "51002"),
        ("database SID mapping", "USE master; BEGIN TRANSACTION;\n" + create_logins
         + f"USE QLDSV; CREATE USER {identifier(temporary)} FOR LOGIN {identifier(other)};\n", "51002"),
    ]
    for description, setup, error in scenarios:
        query = bootstrap.replace("$(QLDSV_ADMIN_LOGIN_HEX)", hex_value(temporary))
        query = query.replace("$(QLDSV_ADMIN_PASSWORD_HEX)", hex_value(password))
        query = query.replace("$(QLDSV_STUDENT_LOGIN_HEX)", hex_value(STUDENT))
        result = sql("sa", None, setup + "GO\n" + query, sa=True, expect_success=False)
        if result.returncode == 0 or ("Msg " + error) not in result.stdout + result.stderr:
            raise RuntimeError("Conflict guard failed: " + description)
        sql("sa", None, f"""
IF SUSER_ID({literal(temporary)}) IS NOT NULL OR SUSER_ID({literal(other)}) IS NOT NULL
 OR DATABASE_PRINCIPAL_ID({literal(temporary)}) IS NOT NULL
 OR DATABASE_PRINCIPAL_ID(N'QLDSV_GIANGVIEN') IS NOT NULL
    THROW 51106, 'Conflict test did not roll back its disposable principals.', 1;
""", sa=True)
        print("PASS collision rejected and rolled back: " + description)


def verify_missing_roles(password):
    # Unique nonexistent names exercise SQL Server's actual NULL results
    # without dropping/changing any production role or membership.
    missing = "__SEC13_missing_" + secrets.token_hex(12)
    sql(ADMIN, password, f"""
IF IS_ROLEMEMBER({literal(missing)}) IS NOT NULL
 OR IS_SRVROLEMEMBER({literal(missing)}) IS NOT NULL
    THROW 51107, 'Negative test requires a nonexistent database/server role.', 1;
""")
    scenarios = [
        ("NULL expected business membership", checked("", missing, ADMIN), False, "51100"),
        ("NULL expected server non-membership", checked("", "QLDSV_ADMIN", ADMIN).replace(
            "IS_SRVROLEMEMBER(N'sysadmin')", f"IS_SRVROLEMEMBER({literal(missing)})"), False, "51100"),
        ("missing Admin metadata membership", metadata_query(admin_role=missing), True, "51104"),
        ("missing Student metadata membership", metadata_query(student_role=missing), True, "51104"),
    ]
    for description, query, use_sa, error in scenarios:
        result = sql("sa" if use_sa else ADMIN, password, query, sa=use_sa, expect_success=False)
        if result.returncode == 0 or ("Msg " + error) not in result.stdout + result.stderr:
            raise RuntimeError("Missing-role verification incorrectly passed: " + description)
        print("PASS verifier rejects " + description)


def build_db_init():
    # Build once, before any compose run or temporary Student password change.
    # Inherit build output so failures remain visible. No credentials in argv.
    print("Building current working tree: docker compose build db-init", flush=True)
    result = subprocess.run(["docker", "compose", "build", "db-init"], cwd=ROOT)
    if result.returncode:
        raise RuntimeError("docker compose build db-init failed; bootstrap reruns were not started.")
    print("PASS db-init built from current working-tree scripts", flush=True)


def verify_admin_policy_guard(admin_password):
    temporary = "__SEC13_policy_" + secrets.token_hex(12)
    password = "Policy#" + secrets.token_hex(20) + "!"
    try:
        sql(ADMIN, admin_password, f"""
USE master;
CREATE LOGIN {identifier(temporary)} WITH PASSWORD={literal(password)}, CHECK_POLICY=OFF;
""")
        env = os.environ.copy()
        env.update(QLDSV_ADMIN_LOGIN_HEX=hex_value(temporary),
                   QLDSV_ADMIN_PASSWORD_HEX=hex_value("Ignored#" + secrets.token_hex(20) + "!"),
                   QLDSV_STUDENT_LOGIN_HEX=hex_value(STUDENT))
        # Run only Security.sql: an expected rejection must not recreate the
        # real common procedures or seed data. This also proves the freshly
        # built image contains the working tree's new policy guard.
        result = run([
            "docker", "compose", "run", "--rm", "--no-deps",
            "-e", "QLDSV_ADMIN_LOGIN_HEX", "-e", "QLDSV_ADMIN_PASSWORD_HEX",
            "-e", "QLDSV_STUDENT_LOGIN_HEX", "--entrypoint", "/bin/bash", "db-init", "-c",
            'export SQLCMDPASSWORD="$MSSQL_SA_PASSWORD"; exec ' + SQLCMD
            + ' -S "$DB_HOST,$DB_PORT" -U sa -C -b -r1 -i /opt/qldsv/database/Security.sql',
        ], env=env)
        if result.returncode == 0 or "Msg 51006" not in result.stdout + result.stderr:
            raise RuntimeError("Fresh-image bootstrap did not reject the CHECK_POLICY=OFF Admin with error 51006.")
        sql("sa", None, f"""
IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name={literal(temporary)}
               AND is_policy_checked=0
               AND PWDCOMPARE(CONVERT(nvarchar(128),{hex_value(password)}),password_hash)=1)
    THROW 51108, 'Rejected disposable Admin policy/password was changed.', 1;
""", sa=True)
    finally:
        sql(ADMIN, admin_password, f"""
IF DATABASE_PRINCIPAL_ID({literal(temporary)}) IS NOT NULL DROP USER {identifier(temporary)};
USE master;
IF SUSER_ID({literal(temporary)}) IS NOT NULL DROP LOGIN {identifier(temporary)};
""")
        sql("sa", None, f"""
IF SUSER_ID({literal(temporary)}) IS NOT NULL OR DATABASE_PRINCIPAL_ID({literal(temporary)}) IS NOT NULL
    THROW 51108, 'Disposable policy-test Login/User cleanup failed.', 1;
""", sa=True)
    print("PASS fresh-image Security.sql: policy-OFF Admin rejected (51006), password/policy unchanged, disposable Login cleaned up")


def change_student(admin_password, new_password):
    sql(ADMIN, admin_password, f"""
USE master;
DECLARE @p nvarchar(128)=CONVERT(nvarchar(128),{hex_value(new_password)});
DECLARE @s nvarchar(max)=N'ALTER LOGIN {identifier(STUDENT)} WITH PASSWORD=N'''
 + REPLACE(@p,N'''',N'''''') + N''';'; EXEC (@s);
""")


def main():
    admin_password = os.environ.get("QLDSV_ADMIN_PASSWORD") or getpass.getpass("Current Admin SQL password: ")
    student_password = os.environ.get("QLDSV_STUDENT_PASSWORD", "123456")
    metadata()
    verify_admin(admin_password)
    verify_student(student_password)
    verify_backup_restore(admin_password)
    verify_conflict_guards()
    verify_missing_roles(admin_password)
    build_db_init()
    verify_admin_policy_guard(admin_password)
    changed_password = "Student#" + secrets.token_hex(20) + "!"
    replacement_admin = "Ignored#" + secrets.token_hex(20) + "!"
    try:
        change_student(admin_password, changed_password)
        verify_student(changed_password)
        env = os.environ.copy()
        env.update(QLDSV_ADMIN_LOGIN=ADMIN, QLDSV_STUDENT_LOGIN=STUDENT,
                   QLDSV_ADMIN_PASSWORD=replacement_admin)
        for iteration in (1, 2):
            result = run(["docker", "compose", "run", "--rm", "--no-deps", "db-init"], env=env)
            if result.returncode:
                # Bootstrap does not print credentials; still keep failures compact.
                raise RuntimeError(f"Bootstrap rerun {iteration} failed; inspect db-init output locally")
            if "password unchanged" not in result.stdout:
                raise RuntimeError("Bootstrap did not report existing Login preservation")
            verify_student(changed_password)
            verify_admin(admin_password)
            if sql(ADMIN, replacement_admin, "SELECT 1;", expect_success=False).returncode == 0:
                raise RuntimeError("Rerun replaced the Admin password")
            if sql(STUDENT, student_password, "SELECT 1;", expect_success=False).returncode == 0:
                raise RuntimeError("Rerun reset the changed Student password")
            print(f"PASS bootstrap rerun {iteration}: existing passwords preserved, changed Student password works")
    finally:
        change_student(admin_password, student_password)
    verify_student(student_password)
    metadata()
    print("PASS cleanup: Student password restored; no permanent test objects/principals")
    print("Epic 1.4 procedure checks: python docker/verify-security-procedures.py")
    print("DEFERRED: application SQL-credential login (Epic 1.5)")


if __name__ == "__main__":
    main()
