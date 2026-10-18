/* Epic 1.4 SECSP-01..06. SQL Server 2014 compatible; rerunnable.
   Caller context throughout: no EXECUTE AS OWNER, TRUSTWORTHY or shared login.
   nvarchar(max) inputs intentionally prevent silent truncation before checks.
   Errors 52000..52099 are application-facing and never echo passwords/SQL.
   Failed mutations roll back the entire transaction, including a caller's
   outer transaction. No business rows are created/deleted here.
*/
USE QLDSV;
GO
IF OBJECT_ID(N'dbo.sp_TaoTaiKhoan', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_TaoTaiKhoan;
GO
CREATE PROCEDURE dbo.sp_TaoTaiKhoan
    @LoginName nvarchar(max),
    @Role nvarchar(max),
    @Password nvarchar(max) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    IF ISNULL(IS_ROLEMEMBER(N'QLDSV_ADMIN'),-1)<>1
       OR ISNULL(IS_ROLEMEMBER(N'QLDSV_SINHVIEN'),-1)<>0
       OR ORIGINAL_LOGIN()<>SUSER_SNAME() OR USER_NAME()<>SUSER_SNAME()
        THROW 52001, 'Only an unambiguous, mapped Admin connection may manage accounts.', 1;
    IF @LoginName IS NULL OR DATALENGTH(@LoginName) NOT BETWEEN 2 AND 256
       OR UNICODE(LEFT(@LoginName,1)) IN (9,10,11,12,13,32,160)
       OR UNICODE(RIGHT(@LoginName,1)) IN (9,10,11,12,13,32,160)
        THROW 52002, 'LoginName must contain 1..128 UTF-16 code units with no surrounding whitespace.', 1;
    DECLARE @Name sysname=CONVERT(sysname,@LoginName), @BusinessRole sysname;
    IF @Name IN (N'sa',N'dbo',N'guest',N'public',N'sys',N'INFORMATION_SCHEMA',
                 N'QLDSV_ADMIN',N'QLDSV_SINHVIEN',N'QLDSV_GIANGVIEN',N'QLDSV_ACCOUNT_ADMIN')
       OR @Name LIKE N'##%' OR @Name LIKE N'db[_]%' OR @Name LIKE N'NT %'
        THROW 52002, 'Reserved/system principal names are not allowed.', 1;
    IF @Role IS NULL OR @Role COLLATE Latin1_General_100_BIN2 NOT IN (N'QLDSV_ADMIN',N'QLDSV_SINHVIEN')
       OR DATALENGTH(@Role)<>DATALENGTH(RTRIM(@Role))
        THROW 52003, 'Role must be exactly QLDSV_ADMIN or QLDSV_SINHVIEN.', 1;
    SET @BusinessRole=CONVERT(sysname,@Role);
    IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name=@BusinessRole AND type='R')
        THROW 52008, 'Expected business role missing; run Security.sql first.', 1;
    IF @BusinessRole=N'QLDSV_SINHVIEN'
    BEGIN
        IF @Password IS NOT NULL AND DATALENGTH(@Password)<>0
            THROW 52006, 'Student Password must be NULL/empty; the assignment default is applied by the server.', 1;
        SET @Password=N'123456';
    END
    ELSE IF @Password IS NULL OR DATALENGTH(@Password) NOT BETWEEN 2 AND 256
        THROW 52006, 'Admin requires a policy-compliant Password of 1..128 UTF-16 code units.', 1;

    DECLARE @sql nvarchar(max), @Error int, @Message nvarchar(2048);
    BEGIN TRY
        BEGIN TRANSACTION;
        -- Keep the Student entity valid until principal creation commits,
        -- including when the caller holds an enclosing transaction open.
        IF @BusinessRole=N'QLDSV_SINHVIEN'
        BEGIN
            IF DATALENGTH(@Name)<>20 OR NOT EXISTS (
                SELECT 1 FROM dbo.Sinhvien WITH (UPDLOCK,HOLDLOCK) WHERE MASV=@Name)
                THROW 52007, 'Student LoginName must be an existing 10-character Sinhvien.MASV.', 1;
        END;
        IF EXISTS (SELECT 1 FROM sys.server_principals WHERE name=@Name)
            THROW 52004, 'Server principal already exists; existing accounts are never repurposed.', 1;
        IF EXISTS (SELECT 1 FROM sys.database_principals WHERE name=@Name)
            THROW 52005, 'Database principal already exists; no automatic SID remapping is allowed.', 1;
        SET @sql=N'CREATE LOGIN '+QUOTENAME(@Name)+N' WITH PASSWORD=N'''
            +REPLACE(@Password,N'''',N'''''')+N''', DEFAULT_DATABASE=[QLDSV], CHECK_EXPIRATION=OFF, CHECK_POLICY='
            +CASE WHEN @BusinessRole=N'QLDSV_ADMIN' THEN N'ON;' ELSE N'OFF;' END;
        EXEC (@sql);
        SET @sql=NULL;
        SET @Password=NULL;
        IF EXISTS (SELECT 1 FROM sys.database_principals WHERE sid=SUSER_SID(@Name))
            THROW 52005, 'Login SID collides with an existing database principal.', 1;
        SET @sql=N'CREATE USER '+QUOTENAME(@Name)+N' FOR LOGIN '+QUOTENAME(@Name)+N' WITH DEFAULT_SCHEMA=dbo;'
            +N'ALTER ROLE '+QUOTENAME(@BusinessRole)+N' ADD MEMBER '+QUOTENAME(@Name)+N';';
        EXEC (@sql);
        IF @BusinessRole=N'QLDSV_ADMIN'
        BEGIN
            SET @sql=N'ALTER SERVER ROLE QLDSV_ACCOUNT_ADMIN ADD MEMBER '+QUOTENAME(@Name)+N';'
                +N'ALTER SERVER ROLE dbcreator ADD MEMBER '+QUOTENAME(@Name)+N';';
            EXEC (@sql);
        END;
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        SET @Error=ERROR_NUMBER();
        IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
        SET @Password=NULL;
        SET @sql=NULL;
        IF @Error BETWEEN 52000 AND 52099 THROW;
        SET @Message=N'Account creation rolled back. Check password policy, principal collisions and delegated server permissions. SQL error '+CONVERT(nvarchar(12),@Error)+N'.';
        THROW 52009, @Message, 1;
    END CATCH;
END;
GO
IF OBJECT_ID(N'dbo.sp_XoaTaiKhoan', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_XoaTaiKhoan;
GO
CREATE PROCEDURE dbo.sp_XoaTaiKhoan
    @LoginName nvarchar(max)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    IF ISNULL(IS_ROLEMEMBER(N'QLDSV_ADMIN'),-1)<>1
       OR ISNULL(IS_ROLEMEMBER(N'QLDSV_SINHVIEN'),-1)<>0
       OR ORIGINAL_LOGIN()<>SUSER_SNAME() OR USER_NAME()<>SUSER_SNAME()
        THROW 52001, 'Only an unambiguous, mapped Admin connection may manage accounts.', 1;
    IF @LoginName IS NULL OR DATALENGTH(@LoginName) NOT BETWEEN 2 AND 256
       OR UNICODE(LEFT(@LoginName,1)) IN (9,10,11,12,13,32,160)
       OR UNICODE(RIGHT(@LoginName,1)) IN (9,10,11,12,13,32,160)
        THROW 52002, 'LoginName must contain 1..128 UTF-16 code units with no surrounding whitespace.', 1;
    DECLARE @Name sysname=CONVERT(sysname,@LoginName), @Sid varbinary(85), @UserId int,
            @LoginId int, @BusinessRole sysname, @sql nvarchar(max), @Error int;
    IF @Name IN (N'sa',N'dbo',N'guest',N'public',N'sys',N'INFORMATION_SCHEMA',
                 N'QLDSV_ADMIN',N'QLDSV_SINHVIEN',N'QLDSV_GIANGVIEN',N'QLDSV_ACCOUNT_ADMIN')
       OR @Name LIKE N'##%' OR @Name LIKE N'db[_]%' OR @Name LIKE N'NT %'
        THROW 52002, 'Reserved/system principal names cannot be deleted.', 1;
    IF @Name=ORIGINAL_LOGIN() OR @Name=SUSER_SNAME() OR @Name=USER_NAME()
        THROW 52014, 'Self-delete is forbidden; use a different Admin connection.', 1;
    BEGIN TRY
        BEGIN TRANSACTION;
        SELECT @Sid=sid,@LoginId=principal_id FROM sys.server_principals
        WHERE name=@Name AND type='S' AND principal_id<>1;
        IF @Sid IS NULL
            THROW 52010, 'Target must be an existing non-system SQL Login (enabled or disabled).', 1;
        SELECT @UserId=principal_id FROM sys.database_principals
        WHERE name=@Name AND type='S' AND authentication_type=1 AND sid=@Sid AND principal_id>4;
        IF @UserId IS NULL
            THROW 52011, 'Target must have a same-name mapped QLDSV User with matching SID.', 1;
        IF (SELECT COUNT(*) FROM sys.database_role_members rm
            JOIN sys.database_principals r ON r.principal_id=rm.role_principal_id
            WHERE rm.member_principal_id=@UserId AND r.name IN (N'QLDSV_ADMIN',N'QLDSV_SINHVIEN'))<>1
           OR EXISTS (SELECT 1 FROM sys.database_role_members rm
                      JOIN sys.database_principals r ON r.principal_id=rm.role_principal_id
                      WHERE rm.member_principal_id=@UserId AND r.name NOT IN (N'QLDSV_ADMIN',N'QLDSV_SINHVIEN'))
            THROW 52012, 'Target must belong to exactly one business role and no unrelated database roles.', 1;
        SELECT @BusinessRole=r.name FROM sys.database_role_members rm
        JOIN sys.database_principals r ON r.principal_id=rm.role_principal_id WHERE rm.member_principal_id=@UserId;
        IF EXISTS (SELECT 1 FROM sys.databases WHERE owner_sid=@Sid)
           OR EXISTS (SELECT 1 FROM sys.schemas WHERE principal_id=@UserId)
           OR EXISTS (SELECT 1 FROM sys.objects WHERE principal_id=@UserId)
           OR EXISTS (SELECT 1 FROM sys.database_principals WHERE owning_principal_id=@UserId)
           OR EXISTS (SELECT 1 FROM sys.server_principals WHERE owning_principal_id=@LoginId)
            THROW 52013, 'Target owns a database, schema, object or role; resolve ownership explicitly first.', 1;
        IF EXISTS (SELECT 1 FROM sys.server_role_members rm
                   JOIN sys.server_principals r ON r.principal_id=rm.role_principal_id
                   WHERE rm.member_principal_id=@LoginId
                     AND (@BusinessRole=N'QLDSV_SINHVIEN' OR r.name NOT IN (N'QLDSV_ACCOUNT_ADMIN',N'dbcreator')))
           OR (@BusinessRole=N'QLDSV_ADMIN' AND
               (NOT EXISTS (SELECT 1 FROM sys.server_role_members WHERE member_principal_id=@LoginId AND role_principal_id=SUSER_ID(N'QLDSV_ACCOUNT_ADMIN'))
                OR NOT EXISTS (SELECT 1 FROM sys.server_role_members WHERE member_principal_id=@LoginId AND role_principal_id=SUSER_ID(N'dbcreator'))))
            THROW 52012, 'Target server-role memberships do not match a managed application account.', 1;
        IF @BusinessRole=N'QLDSV_ADMIN'
        BEGIN
            SET @sql=N'ALTER SERVER ROLE QLDSV_ACCOUNT_ADMIN DROP MEMBER '+QUOTENAME(@Name)+N';'
                +N'ALTER SERVER ROLE dbcreator DROP MEMBER '+QUOTENAME(@Name)+N';';
            EXEC (@sql);
        END;
        SET @sql=N'ALTER ROLE '+QUOTENAME(@BusinessRole)+N' DROP MEMBER '+QUOTENAME(@Name)+N';'
            +N'DROP USER '+QUOTENAME(@Name)+N'; DROP LOGIN '+QUOTENAME(@Name)+N';';
        EXEC (@sql);
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        SET @Error=ERROR_NUMBER();
        IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
        SET @sql=NULL;
        IF @Error BETWEEN 52000 AND 52099 THROW;
        IF @Error=15434
            THROW 52015, 'Account deletion rolled back: target Login has an active session. Close its sessions and retry; no session was killed.', 1;
        THROW 52015, 'Account deletion rolled back. Check active sessions, ownership and delegated server permissions.', 1;
    END CATCH;
END;
GO
IF OBJECT_ID(N'dbo.sp_ThongTinDangNhap', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_ThongTinDangNhap;
GO
CREATE PROCEDURE dbo.sp_ThongTinDangNhap
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @Login sysname=SUSER_SNAME(), @User sysname=USER_NAME(),
            @Admin int=ISNULL(IS_ROLEMEMBER(N'QLDSV_ADMIN'),-1),
            @Student int=ISNULL(IS_ROLEMEMBER(N'QLDSV_SINHVIEN'),-1);
    IF @Login IS NULL OR @User IS NULL OR @Login<>ORIGINAL_LOGIN() OR @Login<>@User
       OR NOT EXISTS (SELECT 1 FROM sys.database_principals
                      WHERE name=@User AND type='S' AND authentication_type=1 AND sid=SUSER_SID() AND principal_id>4)
        THROW 52020, 'Invalid real SQL Login/Database User mapping.', 1;
    IF NOT ((@Admin=1 AND @Student=0) OR (@Admin=0 AND @Student=1))
        THROW 52021, 'Identity must resolve to exactly one business role; missing, NULL or dual membership is invalid.', 1;
    SELECT @Login AS LoginName, @User AS DatabaseUser,
           CONVERT(sysname,CASE WHEN @Admin=1 THEN N'QLDSV_ADMIN' ELSE N'QLDSV_SINHVIEN' END) AS RoleName;
END;
GO
IF OBJECT_ID(N'dbo.sp_SinhVien_XemDiem', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_SinhVien_XemDiem;
GO
CREATE PROCEDURE dbo.sp_SinhVien_XemDiem
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @Student sysname=USER_NAME();
    IF ISNULL(IS_ROLEMEMBER(N'QLDSV_SINHVIEN'),-1)<>1 OR ISNULL(IS_ROLEMEMBER(N'QLDSV_ADMIN'),-1)<>0
       OR @Student<>SUSER_SNAME() OR SUSER_SNAME()<>ORIGINAL_LOGIN()
       OR NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name=@Student AND type='S'
                      AND authentication_type=1 AND sid=SUSER_SID() AND principal_id>4)
        THROW 52022, 'Only an unambiguous, mapped Student connection may view its own exam attempts.', 1;
    IF DATALENGTH(@Student)<>20 OR NOT EXISTS (SELECT 1 FROM dbo.Sinhvien WHERE MASV=@Student)
        THROW 52023, 'Database User does not identify a real Sinhvien.MASV.', 1;
    -- Static, same-owner ownership chain crosses Student's dbo data DENY.
    -- Raw attempts only; no final-score aggregation or absence convention.
    SELECT d.MAMH,m.TENMH,d.LAN,d.DIEM
    FROM dbo.Diem d JOIN dbo.Monhoc m ON m.MAMH=d.MAMH
    JOIN dbo.Sinhvien s ON s.MASV=d.MASV
    WHERE d.MASV=@Student AND s.NGHIHOC=0
    ORDER BY d.MAMH,d.LAN;
END;
GO
GRANT EXECUTE ON OBJECT::dbo.sp_TaoTaiKhoan TO QLDSV_ADMIN;
GRANT EXECUTE ON OBJECT::dbo.sp_XoaTaiKhoan TO QLDSV_ADMIN;
GRANT EXECUTE ON OBJECT::dbo.sp_ThongTinDangNhap TO QLDSV_ADMIN;
GRANT EXECUTE ON OBJECT::dbo.sp_SinhVien_XemDiem TO QLDSV_ADMIN;
DENY EXECUTE ON OBJECT::dbo.sp_TaoTaiKhoan TO QLDSV_SINHVIEN;
DENY EXECUTE ON OBJECT::dbo.sp_XoaTaiKhoan TO QLDSV_SINHVIEN;
GRANT EXECUTE ON OBJECT::dbo.sp_ThongTinDangNhap TO QLDSV_SINHVIEN;
GRANT EXECUTE ON OBJECT::dbo.sp_SinhVien_XemDiem TO QLDSV_SINHVIEN;
PRINT N'Epic 1.4: security procedures and object permissions installed (SECSP-01..06).';
GO
