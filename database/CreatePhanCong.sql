USE QLDSV;
GO

/* ================================================================
   PHAN CONG GIANG DAY

   Mỗi dòng xác định một giảng viên được phân công dạy
   một môn học cho một lớp.

   Khóa chính ghép:
       MAGV + MALOP + MAMH

   Ví dụ:
       GV001 + CNTT01 + CSDL
       = GV001 được dạy môn CSDL cho lớp CNTT01
   ================================================================ */

IF OBJECT_ID(N'dbo.PhanCong', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.PhanCong
    (
        MAGV  NCHAR(10) NOT NULL,
        MALOP NCHAR(8)  NOT NULL,
        MAMH  NCHAR(5)  NOT NULL,

        CONSTRAINT PK_PhanCong
            PRIMARY KEY (MAGV, MALOP, MAMH),

        CONSTRAINT FK_PhanCong_Giangvien
            FOREIGN KEY (MAGV)
            REFERENCES dbo.Giangvien(MAGV),

        CONSTRAINT FK_PhanCong_Lop
            FOREIGN KEY (MALOP)
            REFERENCES dbo.Lop(MALOP),

        CONSTRAINT FK_PhanCong_Monhoc
            FOREIGN KEY (MAMH)
            REFERENCES dbo.Monhoc(MAMH)
    );

    PRINT N'Đã tạo bảng dbo.PhanCong';
END
ELSE
BEGIN
    PRINT N'Bảng dbo.PhanCong đã tồn tại';
END;
GO

PRINT N'================================================';
PRINT N'CREATE PHANCONG HOAN TAT';
PRINT N'================================================';
GO
