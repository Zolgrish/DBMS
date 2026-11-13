/* ================================================================
   PROJECT  : QUẢN LÝ ĐIỂM SINH VIÊN
   DATABASE : QLDSV
   ROLE-BASED STORED PROCEDURES (Admin / Giảng viên / Sinh viên)

   Error codes 55001..55099.
   ================================================================ */

USE QLDSV;
GO

/* ----------------------------------------------------------------
   1. ADMIN: Quản lý Phân công (PhanCong CRUD)
   ---------------------------------------------------------------- */
IF OBJECT_ID(N'dbo.sp_PhanCong_GetAll', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_PhanCong_GetAll;
GO

CREATE PROCEDURE dbo.sp_PhanCong_GetAll
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Caller sysname = ORIGINAL_LOGIN();
    IF NOT EXISTS (
        SELECT 1
        FROM sys.database_principals dp
        JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
        JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
        WHERE dp.sid = SUSER_SID(@Caller) AND r.name = N'QLDSV_ADMIN'
    )
        THROW 55001, N'Chỉ Admin mới có quyền xem toàn bộ phân công.', 1;

    SELECT
        pc.MAGV,
        LTRIM(RTRIM(ISNULL(gv.HO, N'') + N' ' + ISNULL(gv.TEN, N''))) AS HoTenGV,
        pc.MALOP,
        l.TENLOP,
        pc.MAMH,
        mh.TENMH
    FROM dbo.PhanCong pc
    JOIN dbo.Giangvien gv ON gv.MAGV = pc.MAGV
    JOIN dbo.Lop l ON l.MALOP = pc.MALOP
    JOIN dbo.Monhoc mh ON mh.MAMH = pc.MAMH
    ORDER BY pc.MAGV, pc.MALOP, pc.MAMH;
END;
GO


IF OBJECT_ID(N'dbo.sp_PhanCong_Them', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_PhanCong_Them;
GO

CREATE PROCEDURE dbo.sp_PhanCong_Them
(
    @MAGV  NCHAR(10),
    @MALOP NCHAR(8),
    @MAMH  NCHAR(5)
)
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;

    SET @MAGV  = NULLIF(LTRIM(RTRIM(@MAGV)), N'');
    SET @MALOP = NULLIF(LTRIM(RTRIM(@MALOP)), N'');
    SET @MAMH  = NULLIF(LTRIM(RTRIM(@MAMH)), N'');

    DECLARE @Caller sysname = ORIGINAL_LOGIN();
    IF NOT EXISTS (
        SELECT 1
        FROM sys.database_principals dp
        JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
        JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
        WHERE dp.sid = SUSER_SID(@Caller) AND r.name = N'QLDSV_ADMIN'
    )
        THROW 55001, N'Chỉ Admin mới có quyền thêm phân công.', 1;

    IF @MAGV IS NULL OR @MALOP IS NULL OR @MAMH IS NULL
        THROW 55002, N'Vui lòng chọn đầy đủ Giảng viên, Lớp và Môn học.', 1;

    IF NOT EXISTS (SELECT 1 FROM dbo.Giangvien WHERE MAGV = @MAGV)
        THROW 55003, N'Giảng viên không tồn tại.', 1;
    IF NOT EXISTS (SELECT 1 FROM dbo.Lop WHERE MALOP = @MALOP)
        THROW 55004, N'Lớp không tồn tại.', 1;
    IF NOT EXISTS (SELECT 1 FROM dbo.Monhoc WHERE MAMH = @MAMH)
        THROW 55005, N'Môn học không tồn tại.', 1;

    IF EXISTS (SELECT 1 FROM dbo.PhanCong WHERE MAGV = @MAGV AND MALOP = @MALOP AND MAMH = @MAMH)
        THROW 55006, N'Phân công này đã tồn tại.', 1;

    INSERT INTO dbo.PhanCong (MAGV, MALOP, MAMH)
    VALUES (@MAGV, @MALOP, @MAMH);
END;
GO


IF OBJECT_ID(N'dbo.sp_PhanCong_Xoa', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_PhanCong_Xoa;
GO

CREATE PROCEDURE dbo.sp_PhanCong_Xoa
(
    @MAGV  NCHAR(10),
    @MALOP NCHAR(8),
    @MAMH  NCHAR(5)
)
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;

    SET @MAGV  = NULLIF(LTRIM(RTRIM(@MAGV)), N'');
    SET @MALOP = NULLIF(LTRIM(RTRIM(@MALOP)), N'');
    SET @MAMH  = NULLIF(LTRIM(RTRIM(@MAMH)), N'');

    DECLARE @Caller sysname = ORIGINAL_LOGIN();
    IF NOT EXISTS (
        SELECT 1
        FROM sys.database_principals dp
        JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
        JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
        WHERE dp.sid = SUSER_SID(@Caller) AND r.name = N'QLDSV_ADMIN'
    )
        THROW 55001, N'Chỉ Admin mới có quyền xóa phân công.', 1;

    DELETE FROM dbo.PhanCong
    WHERE MAGV = @MAGV AND MALOP = @MALOP AND MAMH = @MAMH;
END;
GO


/* ----------------------------------------------------------------
   2. GIẢNG VIÊN: Hồ sơ cá nhân, Phân công cá nhân, SV lớp đang dạy
   ---------------------------------------------------------------- */
IF OBJECT_ID(N'dbo.sp_GiangVien_XemHoSo', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_GiangVien_XemHoSo;
GO

CREATE PROCEDURE dbo.sp_GiangVien_XemHoSo
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Caller sysname = ORIGINAL_LOGIN();
    IF NOT EXISTS (
        SELECT 1
        FROM sys.database_principals dp
        JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
        JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
        WHERE dp.sid = SUSER_SID(@Caller) AND r.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN')
    )
        THROW 55010, N'Chỉ Giảng viên hoặc Admin mới có quyền xem hồ sơ giảng viên.', 1;

    SELECT MAGV, HO, TEN, PHAI
    FROM dbo.Giangvien
    WHERE MAGV = @Caller;
END;
GO


IF OBJECT_ID(N'dbo.sp_GiangVien_XemPhanCong', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_GiangVien_XemPhanCong;
GO

CREATE PROCEDURE dbo.sp_GiangVien_XemPhanCong
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Caller sysname = ORIGINAL_LOGIN();
    IF NOT EXISTS (
        SELECT 1
        FROM sys.database_principals dp
        JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
        JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
        WHERE dp.sid = SUSER_SID(@Caller) AND r.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN')
    )
        THROW 55010, N'Chỉ Giảng viên hoặc Admin mới có quyền xem phân công cá nhân.', 1;

    SELECT
        pc.MALOP,
        l.TENLOP,
        pc.MAMH,
        mh.TENMH,
        mh.SoTCLT,
        mh.SoTCTH
    FROM dbo.PhanCong pc
    JOIN dbo.Lop l ON l.MALOP = pc.MALOP
    JOIN dbo.Monhoc mh ON mh.MAMH = pc.MAMH
    WHERE pc.MAGV = @Caller
    ORDER BY pc.MALOP, pc.MAMH;
END;
GO


IF OBJECT_ID(N'dbo.sp_GiangVien_XemSinhVienLop', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_GiangVien_XemSinhVienLop;
GO

CREATE PROCEDURE dbo.sp_GiangVien_XemSinhVienLop
(
    @MALOP NCHAR(8)
)
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;

    SET @MALOP = NULLIF(LTRIM(RTRIM(@MALOP)), N'');
    DECLARE @Caller sysname = ORIGINAL_LOGIN();
    DECLARE @IsAdmin bit = 0;
    DECLARE @IsGV bit = 0;

    SELECT
        @IsAdmin = MAX(CASE WHEN r.name = N'QLDSV_ADMIN' THEN 1 ELSE 0 END),
        @IsGV    = MAX(CASE WHEN r.name = N'QLDSV_GIANGVIEN' THEN 1 ELSE 0 END)
    FROM sys.database_principals dp
    JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
    JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
    WHERE dp.sid = SUSER_SID(@Caller)
      AND r.name IN (N'QLDSV_ADMIN', N'QLDSV_GIANGVIEN');

    IF ISNULL(@IsAdmin, 0) = 0 AND ISNULL(@IsGV, 0) = 0
        THROW 55010, N'Không có quyền xem danh sách sinh viên lớp.', 1;

    IF ISNULL(@IsAdmin, 0) = 0
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM dbo.PhanCong WHERE MAGV = @Caller AND MALOP = @MALOP)
            THROW 55011, N'Bạn không được phân công giảng dạy lớp này.', 1;
    END;

    SELECT
        MASV,
        HO,
        TEN,
        MALOP,
        PHAI,
        NGAYSINH,
        NOISINH,
        DIACHI,
        GHICHU
    FROM dbo.Sinhvien
    WHERE MALOP = @MALOP
      AND NGHIHOC = 0
    ORDER BY MASV;
END;
GO


/* ----------------------------------------------------------------
   3. SINH VIÊN: Hồ sơ bản thân, Lớp của mình, Môn học
   ---------------------------------------------------------------- */
IF OBJECT_ID(N'dbo.sp_SinhVien_XemHoSoVaLop', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_SinhVien_XemHoSoVaLop;
GO

CREATE PROCEDURE dbo.sp_SinhVien_XemHoSoVaLop
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Caller sysname = ORIGINAL_LOGIN();
    IF NOT EXISTS (
        SELECT 1
        FROM sys.database_principals dp
        JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
        JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
        WHERE dp.sid = SUSER_SID(@Caller) AND r.name = N'QLDSV_SINHVIEN'
    )
        THROW 55020, N'Chỉ Sinh viên mới có quyền xem hồ sơ sinh viên cá nhân.', 1;

    SELECT
        sv.MASV,
        sv.HO,
        sv.TEN,
        sv.MALOP,
        l.TENLOP,
        sv.PHAI,
        sv.NGAYSINH,
        sv.NOISINH,
        sv.DIACHI,
        sv.GHICHU,
        sv.NGHIHOC
    FROM dbo.Sinhvien sv
    JOIN dbo.Lop l ON l.MALOP = sv.MALOP
    WHERE sv.MASV = @Caller;
END;
GO


IF OBJECT_ID(N'dbo.sp_SinhVien_XemMonHoc', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_SinhVien_XemMonHoc;
GO

CREATE PROCEDURE dbo.sp_SinhVien_XemMonHoc
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Caller sysname = ORIGINAL_LOGIN();
    IF NOT EXISTS (
        SELECT 1
        FROM sys.database_principals dp
        JOIN sys.database_role_members rm ON rm.member_principal_id = dp.principal_id
        JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
        WHERE dp.sid = SUSER_SID(@Caller) AND r.name IN (N'QLDSV_ADMIN', N'QLDSV_SINHVIEN')
    )
        THROW 55020, N'Không có quyền xem danh sách môn học.', 1;

    SELECT MAMH, TENMH, SoTCLT, SoTCTH
    FROM dbo.Monhoc
    ORDER BY MAMH;
END;
GO

GRANT EXECUTE ON OBJECT::dbo.sp_PhanCong_GetAll TO QLDSV_ADMIN;
DENY EXECUTE ON OBJECT::dbo.sp_PhanCong_GetAll TO QLDSV_GIANGVIEN, QLDSV_SINHVIEN;
GRANT EXECUTE ON OBJECT::dbo.sp_PhanCong_Them TO QLDSV_ADMIN;
DENY EXECUTE ON OBJECT::dbo.sp_PhanCong_Them TO QLDSV_GIANGVIEN, QLDSV_SINHVIEN;
GRANT EXECUTE ON OBJECT::dbo.sp_PhanCong_Xoa TO QLDSV_ADMIN;
DENY EXECUTE ON OBJECT::dbo.sp_PhanCong_Xoa TO QLDSV_GIANGVIEN, QLDSV_SINHVIEN;

GRANT EXECUTE ON OBJECT::dbo.sp_GiangVien_XemHoSo TO QLDSV_ADMIN, QLDSV_GIANGVIEN;
DENY EXECUTE ON OBJECT::dbo.sp_GiangVien_XemHoSo TO QLDSV_SINHVIEN;
GRANT EXECUTE ON OBJECT::dbo.sp_GiangVien_XemPhanCong TO QLDSV_ADMIN, QLDSV_GIANGVIEN;
DENY EXECUTE ON OBJECT::dbo.sp_GiangVien_XemPhanCong TO QLDSV_SINHVIEN;
GRANT EXECUTE ON OBJECT::dbo.sp_GiangVien_XemSinhVienLop TO QLDSV_ADMIN, QLDSV_GIANGVIEN;
DENY EXECUTE ON OBJECT::dbo.sp_GiangVien_XemSinhVienLop TO QLDSV_SINHVIEN;

GRANT EXECUTE ON OBJECT::dbo.sp_SinhVien_XemHoSoVaLop TO QLDSV_SINHVIEN;
DENY EXECUTE ON OBJECT::dbo.sp_SinhVien_XemHoSoVaLop TO QLDSV_GIANGVIEN;
GRANT EXECUTE ON OBJECT::dbo.sp_SinhVien_XemMonHoc TO QLDSV_ADMIN, QLDSV_SINHVIEN;
DENY EXECUTE ON OBJECT::dbo.sp_SinhVien_XemMonHoc TO QLDSV_GIANGVIEN;
GO

PRINT N'Role-based Stored Procedures installed successfully.';
GO

