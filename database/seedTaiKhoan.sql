USE QLDSV;
GO


SET NOCOUNT ON;
GO


/* ================================================================
   SEED ACCOUNT

   Password demo:
       123456

   Giai đoạn đồ án:
       lưu plaintext

   Thực tế:
       nên hash password
   ================================================================ */



/* ================================================================
   ADMIN
   ================================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM dbo.TaiKhoan
    WHERE TENDANGNHAP = N'admin'
)

BEGIN

    INSERT INTO dbo.TaiKhoan
    (
        TENDANGNHAP,
        MATKHAU,
        VAITRO
    )

    VALUES
    (
        N'admin',
        N'123456',
        N'Admin'
    );

END;
GO



/* ================================================================
   SINH VIEN
   ================================================================ */


IF NOT EXISTS
(
    SELECT 1
    FROM dbo.TaiKhoan
    WHERE TENDANGNHAP = N'SV00000001'
)

BEGIN

    INSERT INTO dbo.TaiKhoan
    (
        TENDANGNHAP,
        MATKHAU,
        VAITRO,
        MASV
    )

    VALUES
    (
        N'SV00000001',
        N'123456',
        N'SinhVien',
        N'SV00000001'
    );

END;
GO



IF NOT EXISTS
(
    SELECT 1
    FROM dbo.TaiKhoan
    WHERE TENDANGNHAP = N'SV00000002'
)

BEGIN

    INSERT INTO dbo.TaiKhoan
    (
        TENDANGNHAP,
        MATKHAU,
        VAITRO,
        MASV
    )

    VALUES
    (
        N'SV00000002',
        N'123456',
        N'SinhVien',
        N'SV00000002'
    );

END;
GO



/* ================================================================
   GIANG VIEN
   ================================================================ */


IF NOT EXISTS
(
    SELECT 1
    FROM dbo.TaiKhoan
    WHERE TENDANGNHAP = N'GV00000001'
)

BEGIN

    INSERT INTO dbo.TaiKhoan
    (
        TENDANGNHAP,
        MATKHAU,
        VAITRO,
        MAGV
    )

    VALUES
    (
        N'GV00000001',
        N'123456',
        N'GiangVien',
        N'GV00000001'
    );

END;
GO



PRINT N'ADM-01 SEED TAIKHOAN DONE';
GO