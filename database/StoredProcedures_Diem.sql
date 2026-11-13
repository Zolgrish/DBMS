/* ================================================================
   PROJECT  : QUẢN LÝ ĐIỂM SINH VIÊN
   DATABASE : QLDSV
   EPIC 2.5 : STORED PROCEDURES NHẬP ĐIỂM (LẦN 1 & LẦN 2)

   Quy tắc:
   - Admin (QLDSV_ADMIN) được nhập điểm cho mọi lớp và môn học.
   - Giảng viên (QLDSV_GIANGVIEN) chỉ được nhập điểm cho lớp + môn học
     được phân công trong dbo.PhanCong.
   - Sinh viên (QLDSV_SINHVIEN) bị từ chối mọi thao tác.
   - Chỉ thao tác trên sinh viên còn đang học (NGHIHOC = 0).
   ================================================================ */

USE QLDSV;
GO

/* Helper function / inline check pattern:
   Resolve caller's SQL login via ORIGINAL_LOGIN() and verify role.
   Error codes 54001..54099 reserved for Epic 2.5. */

IF OBJECT_ID(N'dbo.sp_Diem_GetLopChoNhapDiem', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_Diem_GetLopChoNhapDiem;
GO

CREATE PROCEDURE dbo.sp_Diem_GetLopChoNhapDiem
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Caller sysname = ORIGINAL_LOGIN();
    DECLARE @DatabaseUser sysname;
    DECLARE @IsAdmin bit = 0;
    DECLARE @IsGV bit = 0;

    IF (
        SELECT COUNT(*)
        FROM sys.database_principals dp
        WHERE dp.sid = SUSER_SID(@Caller)
          AND dp.type = 'S'
          AND dp.authentication_type = 1
          AND dp.principal_id > 4
    ) <> 1
        THROW 54001, N'Không thể xác định Database User của phiên hiện tại.', 1;

    SELECT @DatabaseUser = dp.name
    FROM sys.database_principals dp
    WHERE dp.sid = SUSER_SID(@Caller)
      AND dp.type = 'S'
      AND dp.authentication_type = 1
      AND dp.principal_id > 4;

    SELECT
        @IsAdmin = MAX(CASE WHEN r.name = N'QLDSV_ADMIN' THEN 1 ELSE 0 END),
        @IsGV    = MAX(CASE WHEN r.name = N'QLDSV_GIANGVIEN' THEN 1 ELSE 0 END)
    FROM sys.database_principals dp
    JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
    JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
    WHERE dp.sid = SUSER_SID(@Caller)
      AND r.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN');

    IF ISNULL(@IsAdmin, 0) = 1
    BEGIN
        SELECT MALOP, TENLOP
        FROM dbo.Lop
        ORDER BY MALOP;
        RETURN;
    END;

    IF ISNULL(@IsGV, 0) = 1
    BEGIN
        SELECT DISTINCT l.MALOP, l.TENLOP
        FROM dbo.Lop l
        JOIN dbo.PhanCong pc ON pc.MALOP = l.MALOP
        WHERE pc.MAGV = @DatabaseUser
        ORDER BY l.MALOP;
        RETURN;
    END;

    THROW 54001, N'Chỉ Admin hoặc Giảng viên mới có quyền truy cập chức năng nhập điểm.', 1;
END;
GO


IF OBJECT_ID(N'dbo.sp_Diem_GetMonHocChoNhapDiem', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_Diem_GetMonHocChoNhapDiem;
GO

CREATE PROCEDURE dbo.sp_Diem_GetMonHocChoNhapDiem
(
    @MALOP NCHAR(8)
)
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;

    SET @MALOP = NULLIF(LTRIM(RTRIM(@MALOP)), N'');
    DECLARE @Caller sysname = ORIGINAL_LOGIN();
    DECLARE @DatabaseUser sysname;
    DECLARE @IsAdmin bit = 0;
    DECLARE @IsGV bit = 0;

    IF (
        SELECT COUNT(*)
        FROM sys.database_principals dp
        WHERE dp.sid = SUSER_SID(@Caller)
          AND dp.type = 'S'
          AND dp.authentication_type = 1
          AND dp.principal_id > 4
    ) <> 1
        THROW 54001, N'Không thể xác định Database User của phiên hiện tại.', 1;

    SELECT @DatabaseUser = dp.name
    FROM sys.database_principals dp
    WHERE dp.sid = SUSER_SID(@Caller)
      AND dp.type = 'S'
      AND dp.authentication_type = 1
      AND dp.principal_id > 4;

    SELECT
        @IsAdmin = MAX(CASE WHEN r.name = N'QLDSV_ADMIN' THEN 1 ELSE 0 END),
        @IsGV    = MAX(CASE WHEN r.name = N'QLDSV_GIANGVIEN' THEN 1 ELSE 0 END)
    FROM sys.database_principals dp
    JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
    JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
    WHERE dp.sid = SUSER_SID(@Caller)
      AND r.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN');

    IF ISNULL(@IsAdmin, 0) = 1
    BEGIN
        SELECT MAMH, TENMH, SoTCLT, SoTCTH
        FROM dbo.Monhoc
        ORDER BY MAMH;
        RETURN;
    END;

    IF ISNULL(@IsGV, 0) = 1
    BEGIN
        SELECT DISTINCT mh.MAMH, mh.TENMH, mh.SoTCLT, mh.SoTCTH
        FROM dbo.Monhoc mh
        JOIN dbo.PhanCong pc ON pc.MAMH = mh.MAMH
        WHERE pc.MAGV = @DatabaseUser
          AND (@MALOP IS NULL OR pc.MALOP = @MALOP)
        ORDER BY mh.MAMH;
        RETURN;
    END;

    THROW 54001, N'Chỉ Admin hoặc Giảng viên mới có quyền truy cập chức năng nhập điểm.', 1;
END;
GO


IF OBJECT_ID(N'dbo.sp_Diem_LayDanhSachNhapDiem', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_Diem_LayDanhSachNhapDiem;
GO

CREATE PROCEDURE dbo.sp_Diem_LayDanhSachNhapDiem
(
    @MALOP NCHAR(8),
    @MAMH  NCHAR(5),
    @LAN   SMALLINT
)
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;

    SET @MALOP = NULLIF(LTRIM(RTRIM(@MALOP)), N'');
    SET @MAMH  = NULLIF(LTRIM(RTRIM(@MAMH)), N'');

    IF @MALOP IS NULL OR @MAMH IS NULL OR @LAN NOT IN (1, 2)
        THROW 54002, N'Tham số Lớp, Môn học hoặc Lần thi không hợp lệ.', 1;

    DECLARE @Caller sysname = ORIGINAL_LOGIN();
    DECLARE @DatabaseUser sysname;
    DECLARE @IsAdmin bit = 0;
    DECLARE @IsGV bit = 0;

    IF (
        SELECT COUNT(*)
        FROM sys.database_principals dp
        WHERE dp.sid = SUSER_SID(@Caller)
          AND dp.type = 'S'
          AND dp.authentication_type = 1
          AND dp.principal_id > 4
    ) <> 1
        THROW 54001, N'Không thể xác định Database User của phiên hiện tại.', 1;

    SELECT @DatabaseUser = dp.name
    FROM sys.database_principals dp
    WHERE dp.sid = SUSER_SID(@Caller)
      AND dp.type = 'S'
      AND dp.authentication_type = 1
      AND dp.principal_id > 4;

    SELECT
        @IsAdmin = MAX(CASE WHEN r.name = N'QLDSV_ADMIN' THEN 1 ELSE 0 END),
        @IsGV    = MAX(CASE WHEN r.name = N'QLDSV_GIANGVIEN' THEN 1 ELSE 0 END)
    FROM sys.database_principals dp
    JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
    JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
    WHERE dp.sid = SUSER_SID(@Caller)
      AND r.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN');

    IF ISNULL(@IsAdmin, 0) = 0 AND ISNULL(@IsGV, 0) = 0
        THROW 54001, N'Chỉ Admin hoặc Giảng viên mới có quyền truy cập chức năng nhập điểm.', 1;

    IF ISNULL(@IsAdmin, 0) = 0
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM dbo.PhanCong
            WHERE MAGV = @DatabaseUser AND MALOP = @MALOP AND MAMH = @MAMH
        )
            THROW 54004, N'Bạn không được phân công giảng dạy lớp và môn học này.', 1;
    END;

    IF @LAN = 1
    BEGIN
        SELECT
            sv.MASV,
            sv.HO,
            sv.TEN,
            d.DIEM
        FROM dbo.Sinhvien sv
        LEFT JOIN dbo.Diem d
            ON d.MASV = sv.MASV AND d.MAMH = @MAMH AND d.LAN = 1
        WHERE sv.MALOP = @MALOP
          AND sv.NGHIHOC = 0
        ORDER BY sv.MASV;
        RETURN;
    END;

    -- @LAN = 2:
    -- D2-01: Must have at least one Lan 1 grade record for this class & subject.
    IF NOT EXISTS (
        SELECT 1
        FROM dbo.Diem d1
        JOIN dbo.Sinhvien sv ON sv.MASV = d1.MASV
        WHERE sv.MALOP = @MALOP
          AND d1.MAMH = @MAMH
          AND d1.LAN = 1
    )
    BEGIN
        THROW 54003, N'Chưa nhập điểm lần thi 1 cho lớp và môn học này. Không thể nhập điểm lần 2.', 1;
    END;

    -- D2-02, D2-03, D2-04: Only active students whose Lan 1 score is < 5 or NULL (vắng/chưa thi).
    SELECT
        sv.MASV,
        sv.HO,
        sv.TEN,
        d2.DIEM
    FROM dbo.Sinhvien sv
    LEFT JOIN dbo.Diem d1
        ON d1.MASV = sv.MASV AND d1.MAMH = @MAMH AND d1.LAN = 1
    LEFT JOIN dbo.Diem d2
        ON d2.MASV = sv.MASV AND d2.MAMH = @MAMH AND d2.LAN = 2
    WHERE sv.MALOP = @MALOP
      AND sv.NGHIHOC = 0
      AND (d1.MASV IS NULL OR d1.DIEM IS NULL OR d1.DIEM < 5)
    ORDER BY sv.MASV;
END;
GO


IF OBJECT_ID(N'dbo.sp_Diem_LuuDiem', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_Diem_LuuDiem;
GO

CREATE PROCEDURE dbo.sp_Diem_LuuDiem
(
    @MASV NCHAR(10),
    @MAMH NCHAR(5),
    @LAN  SMALLINT,
    @DIEM FLOAT = NULL
)
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;

    SET @MASV = NULLIF(LTRIM(RTRIM(@MASV)), N'');
    SET @MAMH = NULLIF(LTRIM(RTRIM(@MAMH)), N'');

    IF @MASV IS NULL OR @MAMH IS NULL OR @LAN NOT IN (1, 2)
        THROW 54002, N'Tham số Mã SV, Môn học hoặc Lần thi không hợp lệ.', 1;

    IF @DIEM IS NOT NULL AND (@DIEM < 0 OR @DIEM > 10)
        THROW 54005, N'Điểm phải nằm trong khoảng từ 0 đến 10.', 1;

    DECLARE @MALOP NCHAR(8);
    DECLARE @NGHIHOC BIT;
    SELECT @MALOP = MALOP, @NGHIHOC = NGHIHOC
    FROM dbo.Sinhvien
    WHERE MASV = @MASV;

    IF @MALOP IS NULL
        THROW 54006, N'Không tìm thấy sinh viên.', 1;

    IF @NGHIHOC = 1
        THROW 54007, N'Sinh viên đã nghỉ học; không thể nhập điểm.', 1;

    DECLARE @Caller sysname = ORIGINAL_LOGIN();
    DECLARE @DatabaseUser sysname;
    DECLARE @IsAdmin bit = 0;
    DECLARE @IsGV bit = 0;

    IF (
        SELECT COUNT(*)
        FROM sys.database_principals dp
        WHERE dp.sid = SUSER_SID(@Caller)
          AND dp.type = 'S'
          AND dp.authentication_type = 1
          AND dp.principal_id > 4
    ) <> 1
        THROW 54001, N'Không thể xác định Database User của phiên hiện tại.', 1;

    SELECT @DatabaseUser = dp.name
    FROM sys.database_principals dp
    WHERE dp.sid = SUSER_SID(@Caller)
      AND dp.type = 'S'
      AND dp.authentication_type = 1
      AND dp.principal_id > 4;

    SELECT
        @IsAdmin = MAX(CASE WHEN r.name = N'QLDSV_ADMIN' THEN 1 ELSE 0 END),
        @IsGV    = MAX(CASE WHEN r.name = N'QLDSV_GIANGVIEN' THEN 1 ELSE 0 END)
    FROM sys.database_principals dp
    JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
    JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
    WHERE dp.sid = SUSER_SID(@Caller)
      AND r.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN');

    IF ISNULL(@IsAdmin, 0) = 0 AND ISNULL(@IsGV, 0) = 0
        THROW 54001, N'Chỉ Admin hoặc Giảng viên mới có quyền lưu điểm.', 1;

    IF ISNULL(@IsAdmin, 0) = 0
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM dbo.PhanCong
            WHERE MAGV = @DatabaseUser AND MALOP = @MALOP AND MAMH = @MAMH
        )
            THROW 54004, N'Bạn không được phân công giảng dạy lớp và môn học này.', 1;
    END;

    IF EXISTS (SELECT 1 FROM dbo.Diem WHERE MASV = @MASV AND MAMH = @MAMH AND LAN = @LAN)
    BEGIN
        UPDATE dbo.Diem
        SET DIEM = @DIEM
        WHERE MASV = @MASV AND MAMH = @MAMH AND LAN = @LAN;
    END
    ELSE
    BEGIN
        INSERT INTO dbo.Diem (MASV, MAMH, LAN, DIEM)
        VALUES (@MASV, @MAMH, @LAN, @DIEM);
    END;
END;
GO


IF OBJECT_ID(N'dbo.sp_Diem_XoaDiem', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_Diem_XoaDiem;
GO

CREATE PROCEDURE dbo.sp_Diem_XoaDiem
(
    @MASV NCHAR(10),
    @MAMH NCHAR(5),
    @LAN  SMALLINT
)
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;

    SET @MASV = NULLIF(LTRIM(RTRIM(@MASV)), N'');
    SET @MAMH = NULLIF(LTRIM(RTRIM(@MAMH)), N'');

    IF @MASV IS NULL OR @MAMH IS NULL OR @LAN NOT IN (1, 2)
        THROW 54002, N'Tham số Mã SV, Môn học hoặc Lần thi không hợp lệ.', 1;

    DECLARE @Caller sysname = ORIGINAL_LOGIN();
    DECLARE @IsAdmin bit = 0;

    SELECT
        @IsAdmin = MAX(CASE WHEN r.name = N'QLDSV_ADMIN' THEN 1 ELSE 0 END)
    FROM sys.database_principals dp
    JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
    JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
    WHERE dp.sid = SUSER_SID(@Caller)
      AND r.name = N'QLDSV_ADMIN';

    IF ISNULL(@IsAdmin, 0) <> 1
        THROW 54008, N'Chỉ Admin mới có quyền xóa điểm.', 1;

    DELETE FROM dbo.Diem
    WHERE MASV = @MASV AND MAMH = @MAMH AND LAN = @LAN;
END;
GO

GRANT EXECUTE ON OBJECT::dbo.sp_Diem_GetLopChoNhapDiem TO QLDSV_ADMIN, QLDSV_GIANGVIEN;
GRANT EXECUTE ON OBJECT::dbo.sp_Diem_GetMonHocChoNhapDiem TO QLDSV_ADMIN, QLDSV_GIANGVIEN;
GRANT EXECUTE ON OBJECT::dbo.sp_Diem_LayDanhSachNhapDiem TO QLDSV_ADMIN, QLDSV_GIANGVIEN;
GRANT EXECUTE ON OBJECT::dbo.sp_Diem_LuuDiem TO QLDSV_ADMIN, QLDSV_GIANGVIEN;
GRANT EXECUTE ON OBJECT::dbo.sp_Diem_XoaDiem TO QLDSV_ADMIN;
DENY EXECUTE ON OBJECT::dbo.sp_Diem_XoaDiem TO QLDSV_GIANGVIEN, QLDSV_SINHVIEN;
GO

PRINT N'Epic 2.5: StoredProcedures_Diem installed successfully.';
GO

