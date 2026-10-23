/* Lecturer business CRUD. SQL Server 2022 / compatibility 160; rerunnable DROP/CREATE.
   Caller context only. No SQL account creation/deletion or assignment cascade.
   Mutations roll back the whole transaction (including an enclosing transaction)
   on failure, matching the security procedures' transaction contract.
*/
USE QLDSV;
GO
IF OBJECT_ID(N'dbo.Giangvien',N'U') IS NULL
   OR OBJECT_ID(N'dbo.PhanCong',N'U') IS NULL
   OR OBJECT_ID(N'dbo.sp_GetGiangVien',N'P') IS NULL
   OR (SELECT COUNT(*) FROM sys.database_principals
       WHERE name IN (N'QLDSV_ADMIN',N'QLDSV_GIANGVIEN',N'QLDSV_SINHVIEN')
         AND type='R' AND owning_principal_id=DATABASE_PRINCIPAL_ID(N'dbo'))<>3
   OR NOT EXISTS (SELECT 1 FROM sys.foreign_keys
                  WHERE parent_object_id=OBJECT_ID(N'dbo.PhanCong')
                    AND referenced_object_id=OBJECT_ID(N'dbo.Giangvien')
                    AND is_disabled=0 AND is_not_trusted=0 AND delete_referential_action=0)
    THROW 53009, 'Lecturer module requires core tables, assignment FK, common listing and three business roles.', 1;
GO
IF OBJECT_ID(N'dbo.sp_ThemGiangVien',N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_ThemGiangVien;
GO
CREATE PROCEDURE dbo.sp_ThemGiangVien
    @MAGV nvarchar(max),
    @HO nvarchar(max) = NULL,
    @TEN nvarchar(max) = NULL,
    @PHAI bit = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    IF ISNULL(IS_ROLEMEMBER(N'QLDSV_ADMIN'),-1)<>1
       OR ISNULL(IS_ROLEMEMBER(N'QLDSV_GIANGVIEN'),-1)<>0
       OR ISNULL(IS_ROLEMEMBER(N'QLDSV_SINHVIEN'),-1)<>0
       OR ORIGINAL_LOGIN()<>SUSER_SNAME() OR USER_NAME()<>SUSER_SNAME()
       OR NOT EXISTS (SELECT 1 FROM sys.database_principals
                      WHERE name=USER_NAME() AND type='S' AND authentication_type=1
                        AND sid=SUSER_SID() AND principal_id>4)
       OR (SELECT COUNT(*) FROM sys.database_role_members
           WHERE member_principal_id=DATABASE_PRINCIPAL_ID(USER_NAME()))<>1
        THROW 53001, 'Only an unambiguous mapped Admin may manage lecturer entities.', 1;
    BEGIN TRY
        BEGIN TRANSACTION;
        -- nvarchar(max) prevents parameter truncation before UTF-16 validation.
        IF @MAGV IS NULL OR DATALENGTH(@MAGV)<>20
           OR UNICODE(LEFT(@MAGV,1)) IN (9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288)
           OR UNICODE(RIGHT(@MAGV,1)) IN (9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288)
            THROW 53002, 'MAGV must contain exactly 10 UTF-16 code units without surrounding whitespace.', 1;
        IF DATALENGTH(@HO)>80 OR DATALENGTH(@TEN)>20 OR @PHAI IS NULL
            THROW 53005, 'HO/TEN exceed their NVARCHAR limits or PHAI is missing.', 1;
        SET @HO=NULLIF(LTRIM(RTRIM(@HO)),N'');
        SET @TEN=NULLIF(LTRIM(RTRIM(@TEN)),N'');
        -- Without server metadata visibility, absence cannot be established safely.
        IF ISNULL(HAS_PERMS_BY_NAME(NULL,NULL,N'ALTER ANY LOGIN'),0)<>1
            THROW 53009, 'Admin login metadata permission is required for safe lecturer mutation.', 1;
        IF EXISTS (SELECT 1 FROM dbo.Giangvien WITH (UPDLOCK,HOLDLOCK) WHERE MAGV=@MAGV)
            THROW 53003, 'Lecturer MAGV already exists.', 1;
        IF EXISTS (SELECT 1 FROM sys.server_principals WHERE name=@MAGV)
           OR EXISTS (SELECT 1 FROM sys.database_principals WHERE name=@MAGV)
            THROW 53006, 'SQL Login/User exists. Remove SQL access in Account Management first.', 1;
        INSERT dbo.Giangvien(MAGV,HO,TEN,PHAI) VALUES(@MAGV,@HO,@TEN,@PHAI);
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        DECLARE @Error int=ERROR_NUMBER();
        IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
        IF @Error BETWEEN 53001 AND 53009 THROW;
        IF @Error IN (2601,2627) THROW 53003, 'Lecturer MAGV already exists.', 1;
        THROW 53008, 'Lecturer mutation rolled back; verify prerequisites and database permissions.', 1;
    END CATCH;
END;
GO
IF OBJECT_ID(N'dbo.sp_CapNhatGiangVien',N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_CapNhatGiangVien;
GO
CREATE PROCEDURE dbo.sp_CapNhatGiangVien
    @MAGV nvarchar(max),
    @HO nvarchar(max) = NULL,
    @TEN nvarchar(max) = NULL,
    @PHAI bit = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    IF ISNULL(IS_ROLEMEMBER(N'QLDSV_ADMIN'),-1)<>1
       OR ISNULL(IS_ROLEMEMBER(N'QLDSV_GIANGVIEN'),-1)<>0
       OR ISNULL(IS_ROLEMEMBER(N'QLDSV_SINHVIEN'),-1)<>0
       OR ORIGINAL_LOGIN()<>SUSER_SNAME() OR USER_NAME()<>SUSER_SNAME()
       OR NOT EXISTS (SELECT 1 FROM sys.database_principals
                      WHERE name=USER_NAME() AND type='S' AND authentication_type=1
                        AND sid=SUSER_SID() AND principal_id>4)
       OR (SELECT COUNT(*) FROM sys.database_role_members
           WHERE member_principal_id=DATABASE_PRINCIPAL_ID(USER_NAME()))<>1
        THROW 53001, 'Only an unambiguous mapped Admin may manage lecturer entities.', 1;
    BEGIN TRY
        BEGIN TRANSACTION;
        -- nvarchar(max) prevents parameter truncation before UTF-16 validation.
        IF @MAGV IS NULL OR DATALENGTH(@MAGV)<>20
           OR UNICODE(LEFT(@MAGV,1)) IN (9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288)
           OR UNICODE(RIGHT(@MAGV,1)) IN (9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288)
            THROW 53002, 'MAGV must contain exactly 10 UTF-16 code units without surrounding whitespace.', 1;
        IF DATALENGTH(@HO)>80 OR DATALENGTH(@TEN)>20 OR @PHAI IS NULL
            THROW 53005, 'HO/TEN exceed their NVARCHAR limits or PHAI is missing.', 1;
        SET @HO=NULLIF(LTRIM(RTRIM(@HO)),N'');
        SET @TEN=NULLIF(LTRIM(RTRIM(@TEN)),N'');
        -- Same row/key lock as sp_TaoTaiKhoan's staff entity check.
        IF NOT EXISTS (SELECT 1 FROM dbo.Giangvien WITH (UPDLOCK,HOLDLOCK) WHERE MAGV=@MAGV)
            THROW 53004, 'Lecturer entity was not found.', 1;
        UPDATE dbo.Giangvien SET HO=@HO,TEN=@TEN,PHAI=@PHAI WHERE MAGV=@MAGV;
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        DECLARE @Error int=ERROR_NUMBER();
        IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
        IF @Error BETWEEN 53001 AND 53009 THROW;
        THROW 53008, 'Lecturer mutation rolled back; verify prerequisites and database permissions.', 1;
    END CATCH;
END;
GO
IF OBJECT_ID(N'dbo.sp_XoaGiangVien',N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_XoaGiangVien;
GO
CREATE PROCEDURE dbo.sp_XoaGiangVien
    @MAGV nvarchar(max)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    IF ISNULL(IS_ROLEMEMBER(N'QLDSV_ADMIN'),-1)<>1
       OR ISNULL(IS_ROLEMEMBER(N'QLDSV_GIANGVIEN'),-1)<>0
       OR ISNULL(IS_ROLEMEMBER(N'QLDSV_SINHVIEN'),-1)<>0
       OR ORIGINAL_LOGIN()<>SUSER_SNAME() OR USER_NAME()<>SUSER_SNAME()
       OR NOT EXISTS (SELECT 1 FROM sys.database_principals
                      WHERE name=USER_NAME() AND type='S' AND authentication_type=1
                        AND sid=SUSER_SID() AND principal_id>4)
       OR (SELECT COUNT(*) FROM sys.database_role_members
           WHERE member_principal_id=DATABASE_PRINCIPAL_ID(USER_NAME()))<>1
        THROW 53001, 'Only an unambiguous mapped Admin may manage lecturer entities.', 1;
    BEGIN TRY
        BEGIN TRANSACTION;
        -- nvarchar(max) prevents parameter truncation before UTF-16 validation.
        IF @MAGV IS NULL OR DATALENGTH(@MAGV)<>20
           OR UNICODE(LEFT(@MAGV,1)) IN (9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288)
           OR UNICODE(RIGHT(@MAGV,1)) IN (9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288)
            THROW 53002, 'MAGV must contain exactly 10 UTF-16 code units without surrounding whitespace.', 1;
        -- Same row/key lock as sp_TaoTaiKhoan's staff entity check.
        IF NOT EXISTS (SELECT 1 FROM dbo.Giangvien WITH (UPDLOCK,HOLDLOCK) WHERE MAGV=@MAGV)
            THROW 53004, 'Lecturer entity was not found.', 1;
        -- Without server metadata visibility, absence cannot be established safely.
        IF ISNULL(HAS_PERMS_BY_NAME(NULL,NULL,N'ALTER ANY LOGIN'),0)<>1
            THROW 53009, 'Admin login metadata permission is required for safe lecturer mutation.', 1;
        IF EXISTS (SELECT 1 FROM sys.server_principals WHERE name=@MAGV)
           OR EXISTS (SELECT 1 FROM sys.database_principals WHERE name=@MAGV)
            THROW 53006, 'SQL Login/User exists. Remove SQL access in Account Management first.', 1;
        IF EXISTS (SELECT 1 FROM dbo.PhanCong WITH (UPDLOCK,HOLDLOCK) WHERE MAGV=@MAGV)
            THROW 53007, 'Lecturer still has teaching assignments; remove assignments explicitly first.', 1;
        -- The existing non-cascading assignment FK remains the final protection.
        DELETE FROM dbo.Giangvien WHERE MAGV=@MAGV;
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        DECLARE @Error int=ERROR_NUMBER();
        IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
        IF @Error BETWEEN 53001 AND 53009 THROW;
        IF @Error=547 THROW 53007, 'Lecturer is referenced by teaching assignments.', 1;
        THROW 53008, 'Lecturer mutation rolled back; verify prerequisites and database permissions.', 1;
    END CATCH;
END;
GO
GRANT EXECUTE ON OBJECT::dbo.sp_GetGiangVien TO QLDSV_ADMIN;
DENY EXECUTE ON OBJECT::dbo.sp_GetGiangVien TO QLDSV_GIANGVIEN;
DENY EXECUTE ON OBJECT::dbo.sp_GetGiangVien TO QLDSV_SINHVIEN;
GRANT EXECUTE ON OBJECT::dbo.sp_ThemGiangVien TO QLDSV_ADMIN;
DENY EXECUTE ON OBJECT::dbo.sp_ThemGiangVien TO QLDSV_GIANGVIEN;
DENY EXECUTE ON OBJECT::dbo.sp_ThemGiangVien TO QLDSV_SINHVIEN;
GRANT EXECUTE ON OBJECT::dbo.sp_CapNhatGiangVien TO QLDSV_ADMIN;
DENY EXECUTE ON OBJECT::dbo.sp_CapNhatGiangVien TO QLDSV_GIANGVIEN;
DENY EXECUTE ON OBJECT::dbo.sp_CapNhatGiangVien TO QLDSV_SINHVIEN;
GRANT EXECUTE ON OBJECT::dbo.sp_XoaGiangVien TO QLDSV_ADMIN;
DENY EXECUTE ON OBJECT::dbo.sp_XoaGiangVien TO QLDSV_GIANGVIEN;
DENY EXECUTE ON OBJECT::dbo.sp_XoaGiangVien TO QLDSV_SINHVIEN;
PRINT N'Lecturer business procedures and object permissions installed.';
GO
