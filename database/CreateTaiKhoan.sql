USE QLDSV;
GO


/* ================================================================
   ADM-01
   CREATE TABLE TaiKhoan

   Quy ước:

   Admin:
       MASV NULL
       MAGV NULL

   SinhVien:
       MASV NOT NULL
       MAGV NULL

   GiangVien:
       MASV NULL
       MAGV NOT NULL

   ================================================================ */


IF OBJECT_ID(N'dbo.TaiKhoan', N'U') IS NULL
BEGIN

    CREATE TABLE dbo.TaiKhoan
    (

        TENDANGNHAP NVARCHAR(50) NOT NULL,


        MATKHAU NVARCHAR(255) NOT NULL,


        VAITRO NVARCHAR(20) NOT NULL,


        MASV NCHAR(10) NULL,


        MAGV NCHAR(10) NULL,


        TRANGTHAI BIT NOT NULL
            CONSTRAINT DF_TaiKhoan_TrangThai
            DEFAULT 1,


        NGAYTAO DATETIME NOT NULL
            CONSTRAINT DF_TaiKhoan_NgayTao
            DEFAULT GETDATE(),



        CONSTRAINT PK_TaiKhoan
            PRIMARY KEY (TENDANGNHAP),



        CONSTRAINT CK_TaiKhoan_TENDANGNHAP
            CHECK
            (
                LEN(LTRIM(RTRIM(TENDANGNHAP))) > 0
            ),



        CONSTRAINT CK_TaiKhoan_VAITRO
            CHECK
            (
                VAITRO IN
                (
                    N'Admin',
                    N'SinhVien',
                    N'GiangVien'
                )
            ),



        CONSTRAINT CK_TaiKhoan_LienKet
            CHECK
            (

                (
                    VAITRO = N'Admin'
                    AND MASV IS NULL
                    AND MAGV IS NULL
                )


                OR


                (
                    VAITRO = N'SinhVien'
                    AND MASV IS NOT NULL
                    AND MAGV IS NULL
                )


                OR


                (
                    VAITRO = N'GiangVien'
                    AND MAGV IS NOT NULL
                    AND MASV IS NULL
                )

            )

    );


    PRINT N'Đã tạo bảng dbo.TaiKhoan';

END

ELSE

BEGIN

    PRINT N'Bảng dbo.TaiKhoan đã tồn tại';

END;
GO



/* ================================================================
   FOREIGN KEY Sinhvien
   ================================================================ */


IF NOT EXISTS
(
    SELECT 1
    FROM sys.foreign_keys
    WHERE name = N'FK_TaiKhoan_Sinhvien'
)

BEGIN

    ALTER TABLE dbo.TaiKhoan

    ADD CONSTRAINT FK_TaiKhoan_Sinhvien

    FOREIGN KEY (MASV)

    REFERENCES dbo.Sinhvien(MASV);


    PRINT N'Đã tạo FK_TaiKhoan_Sinhvien';

END;
GO



/* ================================================================
   FOREIGN KEY Giangvien
   ================================================================ */


IF NOT EXISTS
(
    SELECT 1
    FROM sys.foreign_keys
    WHERE name = N'FK_TaiKhoan_Giangvien'
)

BEGIN

    ALTER TABLE dbo.TaiKhoan

    ADD CONSTRAINT FK_TaiKhoan_Giangvien

    FOREIGN KEY (MAGV)

    REFERENCES dbo.Giangvien(MAGV);


    PRINT N'Đã tạo FK_TaiKhoan_Giangvien';

END;
GO



/* ================================================================
   UNIQUE INDEX MASV

   Một sinh viên chỉ có một tài khoản
   ================================================================ */


IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = N'UX_TaiKhoan_MASV'
)

BEGIN

    CREATE UNIQUE INDEX UX_TaiKhoan_MASV

    ON dbo.TaiKhoan(MASV)

    WHERE MASV IS NOT NULL;


    PRINT N'Đã tạo UX_TaiKhoan_MASV';

END;
GO



/* ================================================================
   UNIQUE INDEX MAGV

   Một giảng viên chỉ có một tài khoản
   ================================================================ */


IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = N'UX_TaiKhoan_MAGV'
)

BEGIN

    CREATE UNIQUE INDEX UX_TaiKhoan_MAGV

    ON dbo.TaiKhoan(MAGV)

    WHERE MAGV IS NOT NULL;


    PRINT N'Đã tạo UX_TaiKhoan_MAGV';

END;
GO



PRINT N'================================================';
PRINT N'ADM-01 CREATE TAIKHOAN HOAN TAT';
PRINT N'================================================';
GO