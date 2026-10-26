/* Epic 1.3 (SEC-01..07), SQL Server 2022 target; existing compatibility level is preserved.
   Run with sqlcmd -b (or SSMS SQLCMD mode) as a provisioning principal.
   Required sqlcmd variables: QLDSV_ADMIN_LOGIN_HEX,
   QLDSV_ADMIN_PASSWORD_HEX, QLDSV_STUDENT_LOGIN_HEX.
   Values are 0x-prefixed UTF-16LE hex, encoded by docker/init-db.sh.
   Never enable sqlcmd input echo (-e): the input contains a credential.
   Existing passwords/policy/ownership are never changed.
*/
USE master;
SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @AdminInput nvarchar(max) = CONVERT(nvarchar(max), $(QLDSV_ADMIN_LOGIN_HEX));
DECLARE @StudentInput nvarchar(max) = CONVERT(nvarchar(max), $(QLDSV_STUDENT_LOGIN_HEX));
DECLARE @Password nvarchar(max) = CONVERT(nvarchar(max), $(QLDSV_ADMIN_PASSWORD_HEX));
DECLARE @Admin sysname, @Student sysname, @sql nvarchar(max);

IF CONVERT(int, SERVERPROPERTY('IsIntegratedSecurityOnly')) <> 0
    THROW 51001, 'SEC-01: SQL Authentication/Mixed Mode is required. Configure the server and rerun; this script does not change authentication mode.', 1;
IF DB_ID(N'QLDSV') IS NULL
    THROW 51002, 'SEC-02: QLDSV must exist before Security.sql.', 1;
IF @AdminInput IS NULL OR @StudentInput IS NULL OR DATALENGTH(@AdminInput) <> 20
   OR DATALENGTH(@StudentInput) <> 20
   OR @AdminInput <> LTRIM(RTRIM(@AdminInput))
   OR @StudentInput <> LTRIM(RTRIM(@StudentInput))
   OR @AdminInput = @StudentInput
    THROW 51002, 'SEC-02: Distinct 10-character names required: Admin MAGV and Student MASV.', 1;
SET @Admin = @AdminInput;
SET @Student = @StudentInput;

BEGIN TRY
    BEGIN TRANSACTION;
    -- Reject collisions/elevation, rather than repurposing existing principals.
    IF EXISTS (SELECT 1 FROM sys.server_principals
               WHERE name IN (@Admin, @Student)
                 AND (type <> 'S' OR is_disabled = 1 OR principal_id = 1))
        THROW 51002, 'SEC-02: Existing demo login is not an enabled, non-sa SQL Login. Resolve the collision explicitly.', 1;
    IF EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = @Admin AND is_policy_checked = 0)
        THROW 51006, 'SEC-04: Existing Admin Login has CHECK_POLICY=OFF. An authorized administrator must review it and explicitly enable CHECK_POLICY=ON before rerunning. Bootstrap will not change its policy or password.', 1;
    IF EXISTS (SELECT 1 FROM sys.server_role_members rm
               JOIN sys.server_principals r ON r.principal_id = rm.role_principal_id
               JOIN sys.server_principals m ON m.principal_id = rm.member_principal_id
               WHERE (m.name = @Student) OR (m.name = @Admin AND r.name NOT IN (N'dbcreator', N'QLDSV_ACCOUNT_ADMIN')))
        THROW 51005, 'SEC-04/05: Unexpected server role on a demo login. Remove conflicting membership explicitly before rerunning.', 1;
    IF EXISTS (SELECT 1 FROM sys.server_permissions p
               JOIN sys.server_principals m ON m.principal_id = p.grantee_principal_id
               WHERE m.name = @Student AND p.state IN ('G', 'W')
                 AND p.permission_name NOT IN (N'CONNECT SQL', N'VIEW ANY DATABASE'))
        THROW 51005, 'SEC-05: Student has unexpected server grants. Resolve them explicitly before rerunning.', 1;
    IF EXISTS (SELECT 1 FROM sys.server_permissions p
               JOIN sys.server_principals m ON m.principal_id = p.grantee_principal_id
               WHERE m.name = @Admin AND p.state IN ('G', 'W')
                 AND (p.permission_name NOT IN (N'CONNECT SQL', N'VIEW ANY DATABASE', N'ALTER ANY LOGIN')
                      OR p.state = 'W'))
        THROW 51004, 'SEC-04: Admin has broader server grants than this bootstrap requires. Resolve them explicitly before rerunning.', 1;
    -- Technical server role, separate from the three business database roles.
    IF EXISTS (SELECT 1 FROM sys.server_principals WHERE name=N'QLDSV_ACCOUNT_ADMIN'
               AND (type<>'R' OR is_fixed_role<>0 OR owning_principal_id<>1))
        THROW 51004, 'SEC-04: QLDSV_ACCOUNT_ADMIN must be a user-defined server role owned by the provisioning sa principal.', 1;
    IF EXISTS (SELECT 1 FROM sys.server_role_members WHERE member_principal_id=SUSER_ID(N'QLDSV_ACCOUNT_ADMIN'))
       OR EXISTS (SELECT 1 FROM sys.server_permissions WHERE grantee_principal_id=SUSER_ID(N'QLDSV_ACCOUNT_ADMIN')
                  AND NOT (state='G' AND ((class=100 AND permission_name=N'ALTER ANY LOGIN')
                       OR (class=101 AND major_id=SUSER_ID(N'QLDSV_ACCOUNT_ADMIN') AND permission_name=N'ALTER'))))
        THROW 51004, 'SEC-04: Technical server role has unexpected nesting/permissions; resolve explicitly.', 1;

    USE QLDSV;
    -- Create missing supported roles only; never repair a collision or membership.
    IF EXISTS (SELECT 1 FROM sys.database_principals
               WHERE name IN (N'QLDSV_ADMIN',N'QLDSV_GIANGVIEN',N'QLDSV_SINHVIEN')
                 AND (type<>'R' OR owning_principal_id<>DATABASE_PRINCIPAL_ID(N'dbo')))
        THROW 51003, 'SEC-03: Business role name/type/owner collision; expected database roles owned by dbo.', 1;
    IF DATABASE_PRINCIPAL_ID(N'QLDSV_ADMIN') IS NULL CREATE ROLE QLDSV_ADMIN AUTHORIZATION dbo;
    IF DATABASE_PRINCIPAL_ID(N'QLDSV_GIANGVIEN') IS NULL CREATE ROLE QLDSV_GIANGVIEN AUTHORIZATION dbo;
    IF DATABASE_PRINCIPAL_ID(N'QLDSV_SINHVIEN') IS NULL CREATE ROLE QLDSV_SINHVIEN AUTHORIZATION dbo;
    -- Validate every privileged member, including delegated/non-demo logins.
    -- A missing/ambiguous role lookup is invalid, never implicit authorization.
    IF EXISTS (
        SELECT 1 FROM sys.server_role_members rm
        JOIN sys.server_principals r ON r.principal_id=rm.role_principal_id
        JOIN sys.server_principals m ON m.principal_id=rm.member_principal_id
        WHERE r.name=N'QLDSV_ACCOUNT_ADMIN' AND
              (m.type<>'S' OR m.principal_id=1 OR NOT EXISTS (
                  SELECT 1 FROM sys.database_principals u
                  WHERE u.name=m.name AND u.sid=m.sid AND u.type='S' AND u.authentication_type=1 AND u.principal_id>4
                    AND ISNULL(IS_ROLEMEMBER(N'QLDSV_ADMIN',u.name),-1)=1
                    AND ISNULL(IS_ROLEMEMBER(N'QLDSV_GIANGVIEN',u.name),-1)=0
                    AND ISNULL(IS_ROLEMEMBER(N'QLDSV_SINHVIEN',u.name),-1)=0)))
        THROW 51007, 'SEC-04: Invalid QLDSV_ACCOUNT_ADMIN member. Require a SQL Login mapped by SID to a QLDSV Admin User without Lecturer/Student membership. Review and explicitly correct membership/mapping, then rerun; no automatic changes were made.', 1;
    IF @Admin IN (N'dbo', N'guest', N'public', N'QLDSV_ADMIN', N'QLDSV_SINHVIEN', N'QLDSV_GIANGVIEN', N'QLDSV_ACCOUNT_ADMIN')
       OR @Student IN (N'dbo', N'guest', N'public', N'QLDSV_ADMIN', N'QLDSV_SINHVIEN', N'QLDSV_GIANGVIEN', N'QLDSV_ACCOUNT_ADMIN')
        THROW 51002, 'SEC-02: Reserved principal name.', 1;
    IF NOT EXISTS (SELECT 1 FROM dbo.Giangvien WITH (UPDLOCK,HOLDLOCK) WHERE MAGV = @Admin)
        THROW 51002, 'SEC-02: Bootstrap Admin must match an existing Giangvien.MAGV.', 1;
    IF NOT EXISTS (SELECT 1 FROM dbo.Sinhvien WITH (UPDLOCK,HOLDLOCK) WHERE MASV = @Student)
        THROW 51002, 'SEC-02: Student demo login must match an existing Sinhvien.MASV. Run seedData.sql first.', 1;
    IF EXISTS (SELECT 1 FROM sys.databases WHERE database_id = DB_ID()
               AND owner_sid IN (SUSER_SID(@Admin), SUSER_SID(@Student)))
        THROW 51002, 'SEC-02: A demo login owns QLDSV; expected a separate mapped database user.', 1;
    IF EXISTS (SELECT 1 FROM sys.database_principals
               WHERE name IN (@Admin, @Student)
                 AND (type <> 'S' OR authentication_type <> 1
                      OR SUSER_SID(name) IS NULL OR sid <> SUSER_SID(name)))
        THROW 51002, 'SEC-02: Existing database user has incompatible type/SID/login mapping. No automatic remap performed.', 1;
    IF EXISTS (SELECT 1 FROM sys.database_principals
               WHERE sid IN (SUSER_SID(@Admin), SUSER_SID(@Student))
                 AND name NOT IN (@Admin, @Student))
        THROW 51002, 'SEC-02: Login SID already maps to a differently named database user.', 1;
    IF EXISTS (SELECT 1 FROM sys.database_role_members rm
               JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
               JOIN sys.database_principals m ON m.principal_id = rm.member_principal_id
               WHERE (m.name = @Admin AND r.name <> N'QLDSV_ADMIN')
                  OR (m.name = @Student AND r.name <> N'QLDSV_SINHVIEN')
                  OR m.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN', N'QLDSV_SINHVIEN'))
        THROW 51003, 'SEC-03: Conflicting/nested database role membership exists. Resolve it explicitly; application users must belong to exactly one of three business roles.', 1;
    IF EXISTS (SELECT 1 FROM sys.schemas
               WHERE principal_id IN (DATABASE_PRINCIPAL_ID(@Student), DATABASE_PRINCIPAL_ID(N'QLDSV_SINHVIEN')))
       OR EXISTS (SELECT 1 FROM sys.objects
                  WHERE principal_id IN (DATABASE_PRINCIPAL_ID(@Student), DATABASE_PRINCIPAL_ID(N'QLDSV_SINHVIEN')))
        THROW 51005, 'SEC-05: Student user/role must not own schemas or objects.', 1;
    -- All existing application members must already satisfy the identity and
    -- privilege contracts. Drift is reported, never silently remapped/repaired.
    IF EXISTS (
        SELECT 1 FROM sys.database_role_members rm
        JOIN sys.database_principals r ON r.principal_id=rm.role_principal_id
        JOIN sys.database_principals u ON u.principal_id=rm.member_principal_id
        WHERE r.name IN (N'QLDSV_ADMIN',N'QLDSV_GIANGVIEN',N'QLDSV_SINHVIEN') AND (
            u.type<>'S' OR u.authentication_type<>1 OR u.principal_id<=4
            OR SUSER_SID(u.name) IS NULL OR u.sid<>SUSER_SID(u.name)
            OR DATALENGTH(u.name)<>20
            OR (SELECT COUNT(*) FROM sys.database_role_members x
                JOIN sys.database_principals y ON y.principal_id=x.role_principal_id
                WHERE x.member_principal_id=u.principal_id)<>1
            OR (r.name IN (N'QLDSV_ADMIN',N'QLDSV_GIANGVIEN')
                AND NOT EXISTS (SELECT 1 FROM dbo.Giangvien WITH (UPDLOCK,HOLDLOCK) WHERE MAGV=u.name))
            OR (r.name=N'QLDSV_SINHVIEN'
                AND NOT EXISTS (SELECT 1 FROM dbo.Sinhvien WITH (UPDLOCK,HOLDLOCK) WHERE MASV=u.name))))
        THROW 51003, 'SEC-03: Application User has invalid Login/User/SID/entity or multiple/unrelated roles. Resolve explicitly; no automatic repair.', 1;
    IF EXISTS (
        SELECT 1 FROM sys.database_role_members rm
        JOIN sys.database_principals r ON r.principal_id=rm.role_principal_id
        JOIN sys.database_principals u ON u.principal_id=rm.member_principal_id
        JOIN sys.sql_logins l ON l.sid=u.sid AND l.name=u.name
        WHERE r.name IN (N'QLDSV_ADMIN',N'QLDSV_GIANGVIEN',N'QLDSV_SINHVIEN') AND (
            (r.name IN (N'QLDSV_ADMIN',N'QLDSV_GIANGVIEN') AND l.is_policy_checked<>1)
            OR (r.name=N'QLDSV_SINHVIEN' AND l.is_policy_checked<>0)
            OR EXISTS (SELECT 1 FROM sys.server_role_members sm
                       JOIN sys.server_principals sr ON sr.principal_id=sm.role_principal_id
                       WHERE sm.member_principal_id=l.principal_id
                       AND (r.name<>N'QLDSV_ADMIN' OR sr.name NOT IN (N'QLDSV_ACCOUNT_ADMIN',N'dbcreator')))
            OR (r.name=N'QLDSV_ADMIN' AND (
                NOT EXISTS (SELECT 1 FROM sys.server_role_members WHERE member_principal_id=l.principal_id AND role_principal_id=SUSER_ID(N'QLDSV_ACCOUNT_ADMIN'))
                OR NOT EXISTS (SELECT 1 FROM sys.server_role_members WHERE member_principal_id=l.principal_id AND role_principal_id=SUSER_ID(N'dbcreator'))))
            OR (r.name<>N'QLDSV_ADMIN' AND EXISTS (
                SELECT 1 FROM sys.server_permissions WHERE grantee_principal_id=l.principal_id
                AND state IN ('G','W') AND permission_name NOT IN (N'CONNECT SQL',N'VIEW ANY DATABASE')))))
        THROW 51005, 'SEC-04/05: Application Login password policy/server privileges drift. Resolve explicitly; policy/password unchanged.', 1;
    IF EXISTS (SELECT 1 FROM sys.database_principals u
               WHERE (u.name=N'QLDSV_GIANGVIEN' OR IS_ROLEMEMBER(N'QLDSV_GIANGVIEN',u.name)=1)
               AND (EXISTS (SELECT 1 FROM sys.schemas WHERE principal_id=u.principal_id)
                    OR EXISTS (SELECT 1 FROM sys.objects WHERE principal_id=u.principal_id)))
       OR EXISTS (SELECT 1 FROM sys.database_permissions p JOIN sys.database_principals u ON u.principal_id=p.grantee_principal_id
                  WHERE (u.name=N'QLDSV_GIANGVIEN' OR IS_ROLEMEMBER(N'QLDSV_GIANGVIEN',u.name)=1)
                  AND p.state IN ('G','W') AND NOT (
                    (p.class=0 AND p.permission_name=N'CONNECT' AND p.state='G') OR
                    (p.class=1 AND p.major_id IN (ISNULL(OBJECT_ID(N'dbo.sp_ThongTinDangNhap'),-1),
                                                ISNULL(OBJECT_ID(N'dbo.sp_DoiMatKhau'),-1))
                     AND p.permission_name=N'EXECUTE' AND p.state='G')))
        THROW 51005, 'SEC-05: Lecturer has unexpected ownership/grants. Resolve explicitly before rerunning.', 1;
    -- Only the safe Epic 1.4/1.7 object grants; never broad EXECUTE.
    IF EXISTS (SELECT 1 FROM sys.database_permissions p
               WHERE p.grantee_principal_id IN (DATABASE_PRINCIPAL_ID(@Student), DATABASE_PRINCIPAL_ID(N'QLDSV_SINHVIEN'))
                 AND p.state IN ('G', 'W') AND NOT
                 ((p.class = 0 AND p.permission_name = N'CONNECT') OR
                  (p.class = 1 AND p.major_id IN (ISNULL(OBJECT_ID(N'dbo.sp_SinhVien_XemDiem'), -1),
                                                ISNULL(OBJECT_ID(N'dbo.sp_ThongTinDangNhap'), -1),
                                                ISNULL(OBJECT_ID(N'dbo.sp_DoiMatKhau'), -1))
                   AND p.permission_name = N'EXECUTE' AND p.state = 'G')))
        THROW 51005, 'SEC-05: Unexpected Student grants exist. Remove unsafe grants explicitly before rerunning.', 1;

    USE master;
    IF SUSER_ID(@Admin) IS NULL
    BEGIN
        IF DATALENGTH(@Password) NOT BETWEEN 2 AND 256
            THROW 51002, 'SEC-02: QLDSV_ADMIN_PASSWORD is required (1..128 UTF-16 code units) when creating the Admin login.', 1;
        SET @sql = N'CREATE LOGIN ' + QUOTENAME(@Admin)
            + N' WITH PASSWORD = N''' + REPLACE(@Password, N'''', N'''''')
            + N''', CHECK_POLICY = ON, CHECK_EXPIRATION = OFF, DEFAULT_DATABASE = [QLDSV];';
        BEGIN TRY
            EXEC (@sql);
        END TRY
        BEGIN CATCH
            -- Do not echo SQL text/credential on a password policy failure.
            THROW 51002, 'SEC-02: Admin Login creation failed. Supply a strong policy-compliant password and verify provisioning rights.', 1;
        END CATCH;
        PRINT N'SEC-02: Created Admin SQL Login (password policy ON).';
    END
    ELSE PRINT N'SEC-02: Verified existing Admin SQL Login; password unchanged.';
    SET @Password = NULL;
    SET @sql = NULL;
    IF SUSER_ID(@Student) IS NULL
    BEGIN
        SET @sql = N'CREATE LOGIN ' + QUOTENAME(@Student)
            + N' WITH PASSWORD = ''123456'', CHECK_POLICY = OFF, CHECK_EXPIRATION = OFF, DEFAULT_DATABASE = [QLDSV];';
        EXEC (@sql);
        PRINT N'SEC-02: Created Student demo SQL Login (assignment default; policy OFF only for Student).';
    END
    ELSE PRINT N'SEC-02: Verified existing Student SQL Login; password unchanged.';
    IF SUSER_ID(N'QLDSV_ACCOUNT_ADMIN') IS NULL
    BEGIN
        SET @sql=N'CREATE SERVER ROLE QLDSV_ACCOUNT_ADMIN AUTHORIZATION '+QUOTENAME(SUSER_NAME(1))+N';';
        EXEC (@sql);
    END;
    GRANT ALTER ANY LOGIN TO QLDSV_ACCOUNT_ADMIN;
    GRANT ALTER ON SERVER ROLE::QLDSV_ACCOUNT_ADMIN TO QLDSV_ACCOUNT_ADMIN;
    IF NOT EXISTS (SELECT 1 FROM sys.server_role_members
                   WHERE role_principal_id=SUSER_ID(N'QLDSV_ACCOUNT_ADMIN') AND member_principal_id=SUSER_ID(@Admin))
    BEGIN
        SET @sql=N'ALTER SERVER ROLE QLDSV_ACCOUNT_ADMIN ADD MEMBER '+QUOTENAME(@Admin)+N';';
        EXEC (@sql);
    END;
    -- Migrate Epic 1.3's direct grant to the inherited technical-role grant.
    SET @sql = N'REVOKE ALTER ANY LOGIN FROM ' + QUOTENAME(@Admin) + N';';
    EXEC (@sql);
    IF NOT EXISTS (SELECT 1 FROM sys.server_role_members
                   WHERE role_principal_id = SUSER_ID(N'dbcreator') AND member_principal_id = SUSER_ID(@Admin))
    BEGIN
        SET @sql = N'ALTER SERVER ROLE [dbcreator] ADD MEMBER ' + QUOTENAME(@Admin) + N';';
        EXEC (@sql);
    END;

    USE QLDSV;
    IF DATABASE_PRINCIPAL_ID(@Admin) IS NULL
    BEGIN
        SET @sql = N'CREATE USER ' + QUOTENAME(@Admin) + N' FOR LOGIN ' + QUOTENAME(@Admin) + N' WITH DEFAULT_SCHEMA = dbo;';
        EXEC (@sql);
    END;
    IF DATABASE_PRINCIPAL_ID(@Student) IS NULL
    BEGIN
        SET @sql = N'CREATE USER ' + QUOTENAME(@Student) + N' FOR LOGIN ' + QUOTENAME(@Student) + N' WITH DEFAULT_SCHEMA = dbo;';
        EXEC (@sql);
    END;
    IF NOT EXISTS (SELECT 1 FROM sys.database_role_members
                   WHERE role_principal_id = DATABASE_PRINCIPAL_ID(N'QLDSV_ADMIN') AND member_principal_id = DATABASE_PRINCIPAL_ID(@Admin))
    BEGIN
        SET @sql = N'ALTER ROLE QLDSV_ADMIN ADD MEMBER ' + QUOTENAME(@Admin) + N';';
        EXEC (@sql);
    END;
    IF NOT EXISTS (SELECT 1 FROM sys.database_role_members
                   WHERE role_principal_id = DATABASE_PRINCIPAL_ID(N'QLDSV_SINHVIEN') AND member_principal_id = DATABASE_PRINCIPAL_ID(@Student))
    BEGIN
        SET @sql = N'ALTER ROLE QLDSV_SINHVIEN ADD MEMBER ' + QUOTENAME(@Student) + N';';
        EXEC (@sql);
    END;
    GRANT CONNECT TO QLDSV_GIANGVIEN;
    DENY SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo TO QLDSV_GIANGVIEN;
    GRANT CONNECT TO QLDSV_ADMIN;
    GRANT CONNECT TO QLDSV_SINHVIEN;
    GRANT CONTROL ON DATABASE::QLDSV TO QLDSV_ADMIN;
    DENY SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo TO QLDSV_SINHVIEN;

    -- Object-specific EXECUTE denials survive public/broader execute grants.
    -- No schema-wide EXECUTE grant OR deny: Epic 1.4 can grant its safe SP.
    DENY EXECUTE ON OBJECT::dbo.sp_GetLop TO QLDSV_SINHVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_GetLop TO QLDSV_GIANGVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_GetMonHoc TO QLDSV_SINHVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_GetMonHoc TO QLDSV_GIANGVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_GetGiangVien TO QLDSV_SINHVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_GetGiangVien TO QLDSV_GIANGVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_GetSinhVienByLop TO QLDSV_SINHVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_GetSinhVienByLop TO QLDSV_GIANGVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_GetSinhVienByMa TO QLDSV_SINHVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_GetSinhVienByMa TO QLDSV_GIANGVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_CheckMaSV TO QLDSV_SINHVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_CheckMaSV TO QLDSV_GIANGVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_CheckMaLop TO QLDSV_SINHVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_CheckMaLop TO QLDSV_GIANGVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_CheckMaMH TO QLDSV_SINHVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_CheckMaMH TO QLDSV_GIANGVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_GetActiveStudents TO QLDSV_SINHVIEN;
    DENY EXECUTE ON OBJECT::dbo.sp_GetActiveStudents TO QLDSV_GIANGVIEN;
    COMMIT TRANSACTION;
    PRINT N'SEC-01..06: Security bootstrap complete. Admin: CONTROL DATABASE, QLDSV_ACCOUNT_ADMIN (ALTER ANY LOGIN/self-ALTER), dbcreator; Lecturer/Student: CONNECT, data/common-SP denials.';
    PRINT N'SEC-07: Run real-principal verification; security procedures run next. Application SQL login waits for Epic 1.5.';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    SET @Password = NULL;
    SET @sql = NULL;
    THROW;
END CATCH;
GO
