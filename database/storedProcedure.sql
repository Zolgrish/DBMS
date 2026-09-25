/* ================================================================
   PROJECT  : QUẢN LÝ ĐIỂM SINH VIÊN
   DATABASE : QLDSV
   EPIC 1.2 : STORED PROCEDURE DÙNG CHUNG

   SP-01 -> SP-09

   Điều chỉnh:
   - Ghi rõ schema dbo
   - Chuẩn hóa @MALOP rỗng / khoảng trắng
   - Tương thích SQL Server cũ:
         OBJECT_ID + DROP PROCEDURE + CREATE PROCEDURE
   ================================================================ */

USE QLDSV;
GO


/* ================================================================
   SP-01
   dbo.sp_GetLop

   Công dụng:
   - Lấy danh sách lớp
   - Dùng cho ComboBox / danh mục lớp / báo cáo
   ================================================================ */

IF OBJECT_ID(N'dbo.sp_GetLop', N'P') IS NOT NULL
BEGIN
    DROP PROCEDURE dbo.sp_GetLop;
END;
GO

CREATE PROCEDURE dbo.sp_GetLop
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        MALOP,
        TENLOP
    FROM dbo.Lop
    ORDER BY MALOP;
END;
GO


/* ================================================================
   SP-02
   dbo.sp_GetMonHoc

   Công dụng:
   - Lấy danh sách môn học
   ================================================================ */

IF OBJECT_ID(N'dbo.sp_GetMonHoc', N'P') IS NOT NULL
BEGIN
    DROP PROCEDURE dbo.sp_GetMonHoc;
END;
GO

CREATE PROCEDURE dbo.sp_GetMonHoc
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        MAMH,
        TENMH,
        SoTCLT,
        SoTCTH
    FROM dbo.Monhoc
    ORDER BY MAMH;
END;
GO


/* ================================================================
   SP-03
   dbo.sp_GetGiangVien

   Công dụng:
   - Lấy danh sách giảng viên
   ================================================================ */

IF OBJECT_ID(N'dbo.sp_GetGiangVien', N'P') IS NOT NULL
BEGIN
    DROP PROCEDURE dbo.sp_GetGiangVien;
END;
GO

CREATE PROCEDURE dbo.sp_GetGiangVien
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        MAGV,
        HO,
        TEN,
        PHAI
    FROM dbo.Giangvien
    ORDER BY MAGV;
END;
GO


/* ================================================================
   SP-04
   dbo.sp_GetSinhVienByLop

   Input:
       @MALOP NCHAR(8)

   Công dụng:
   - Lấy toàn bộ sinh viên thuộc một lớp
   - Bao gồm cả sinh viên đã nghỉ học vì đây là SP phục vụ
     quản lý danh sách sinh viên

   Quy tắc:
   - NULL / '' / chỉ khoảng trắng => trả 0 dòng
   ================================================================ */

IF OBJECT_ID(N'dbo.sp_GetSinhVienByLop', N'P') IS NOT NULL
BEGIN
    DROP PROCEDURE dbo.sp_GetSinhVienByLop;
END;
GO

CREATE PROCEDURE dbo.sp_GetSinhVienByLop
(
    @MALOP NCHAR(8)
)
AS
BEGIN
    SET NOCOUNT ON;

    -- Chuẩn hóa:
    -- NULL       -> NULL
    -- ''         -> NULL
    -- '   '      -> NULL
    SET @MALOP = NULLIF(
        LTRIM(RTRIM(@MALOP)),
        N''
    );

    SELECT
        MASV,
        HO,
        TEN,
        MALOP,
        PHAI,
        NGAYSINH,
        NOISINH,
        DIACHI,
        GHICHU,
        NGHIHOC,
        HINH
    FROM dbo.Sinhvien
    WHERE @MALOP IS NOT NULL
      AND MALOP = @MALOP
    ORDER BY MASV;
END;
GO


/* ================================================================
   SP-05
   dbo.sp_GetSinhVienByMa

   Input:
       @MASV NCHAR(10)

   Công dụng:
   - Tra cứu một sinh viên theo mã
   ================================================================ */

IF OBJECT_ID(N'dbo.sp_GetSinhVienByMa', N'P') IS NOT NULL
BEGIN
    DROP PROCEDURE dbo.sp_GetSinhVienByMa;
END;
GO

CREATE PROCEDURE dbo.sp_GetSinhVienByMa
(
    @MASV NCHAR(10)
)
AS
BEGIN
    SET NOCOUNT ON;

    SET @MASV = NULLIF(
        LTRIM(RTRIM(@MASV)),
        N''
    );

    SELECT
        MASV,
        HO,
        TEN,
        MALOP,
        PHAI,
        NGAYSINH,
        NOISINH,
        DIACHI,
        GHICHU,
        NGHIHOC,
        HINH
    FROM dbo.Sinhvien
    WHERE @MASV IS NOT NULL
      AND MASV = @MASV;
END;
GO


/* ================================================================
   SP-06
   dbo.sp_CheckMaSV

   Input:
       @MASV NCHAR(10)

   Return result set:
       Result = 1 : MASV đã tồn tại
       Result = 0 : MASV chưa tồn tại

   NULL / chuỗi rỗng:
       Result = 0
   ================================================================ */

IF OBJECT_ID(N'dbo.sp_CheckMaSV', N'P') IS NOT NULL
BEGIN
    DROP PROCEDURE dbo.sp_CheckMaSV;
END;
GO

CREATE PROCEDURE dbo.sp_CheckMaSV
(
    @MASV NCHAR(10)
)
AS
BEGIN
    SET NOCOUNT ON;

    SET @MASV = NULLIF(
        LTRIM(RTRIM(@MASV)),
        N''
    );

    IF @MASV IS NOT NULL
       AND EXISTS
       (
           SELECT 1
           FROM dbo.Sinhvien
           WHERE MASV = @MASV
       )
    BEGIN
        SELECT CAST(1 AS BIT) AS Result;
    END
    ELSE
    BEGIN
        SELECT CAST(0 AS BIT) AS Result;
    END;
END;
GO


/* ================================================================
   SP-07
   dbo.sp_CheckMaLop

   Input:
       @MALOP NCHAR(8)

   Return:
       Result = 1 : lớp tồn tại
       Result = 0 : lớp không tồn tại
   ================================================================ */

IF OBJECT_ID(N'dbo.sp_CheckMaLop', N'P') IS NOT NULL
BEGIN
    DROP PROCEDURE dbo.sp_CheckMaLop;
END;
GO

CREATE PROCEDURE dbo.sp_CheckMaLop
(
    @MALOP NCHAR(8)
)
AS
BEGIN
    SET NOCOUNT ON;

    SET @MALOP = NULLIF(
        LTRIM(RTRIM(@MALOP)),
        N''
    );

    IF @MALOP IS NOT NULL
       AND EXISTS
       (
           SELECT 1
           FROM dbo.Lop
           WHERE MALOP = @MALOP
       )
    BEGIN
        SELECT CAST(1 AS BIT) AS Result;
    END
    ELSE
    BEGIN
        SELECT CAST(0 AS BIT) AS Result;
    END;
END;
GO


/* ================================================================
   SP-08
   dbo.sp_CheckMaMH

   Input:
       @MAMH NCHAR(5)

   Return:
       Result = 1 : môn tồn tại
       Result = 0 : môn không tồn tại
   ================================================================ */

IF OBJECT_ID(N'dbo.sp_CheckMaMH', N'P') IS NOT NULL
BEGIN
    DROP PROCEDURE dbo.sp_CheckMaMH;
END;
GO

CREATE PROCEDURE dbo.sp_CheckMaMH
(
    @MAMH NCHAR(5)
)
AS
BEGIN
    SET NOCOUNT ON;

    SET @MAMH = NULLIF(
        LTRIM(RTRIM(@MAMH)),
        N''
    );

    IF @MAMH IS NOT NULL
       AND EXISTS
       (
           SELECT 1
           FROM dbo.Monhoc
           WHERE MAMH = @MAMH
       )
    BEGIN
        SELECT CAST(1 AS BIT) AS Result;
    END
    ELSE
    BEGIN
        SELECT CAST(0 AS BIT) AS Result;
    END;
END;
GO


/* ================================================================
   SP-09
   dbo.sp_GetActiveStudents

   Công dụng:
   - Chỉ lấy sinh viên còn đang học:
         NGHIHOC = 0

   @MALOP có thể:
       NULL       -> tất cả lớp
       ''         -> tất cả lớp
       '   '      -> tất cả lớp
       'CNTT01'   -> chỉ lớp CNTT01

   Đây là SP dành cho các nghiệp vụ chính như:
   - Nhập điểm
   - Danh sách thi
   - Báo cáo
   - Tổng hợp điểm
   ================================================================ */

IF OBJECT_ID(N'dbo.sp_GetActiveStudents', N'P') IS NOT NULL
BEGIN
    DROP PROCEDURE dbo.sp_GetActiveStudents;
END;
GO

CREATE PROCEDURE dbo.sp_GetActiveStudents
(
    @MALOP NCHAR(8) = NULL
)
AS
BEGIN
    SET NOCOUNT ON;

    SET @MALOP = NULLIF(
        LTRIM(RTRIM(@MALOP)),
        N''
    );

    SELECT
        MASV,
        HO,
        TEN,
        MALOP,
        PHAI,
        NGAYSINH,
        NOISINH,
        DIACHI,
        GHICHU,
        HINH
    FROM dbo.Sinhvien
    WHERE NGHIHOC = 0
      AND
      (
          @MALOP IS NULL
          OR MALOP = @MALOP
      )
    ORDER BY MALOP, MASV;
END;
GO


PRINT N'=====================================================';
PRINT N'QLDSV - EPIC 1.2';
PRINT N'Đã tạo SP-01 -> SP-09 thành công.';
PRINT N'=====================================================';
GO