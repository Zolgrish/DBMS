IF DB_ID(N'QLDSV') IS NULL
BEGIN
    CREATE DATABASE QLDSV;
END
GO

USE QLDSV;
GO


/* ================================================================
   DB-02
   TẠO BẢNG LOP

   MALOP  : NCHAR(8) - Primary Key
   TENLOP : NVARCHAR(40) - Unique
   ================================================================ */

CREATE TABLE Lop
(
    MALOP  NCHAR(8)      NOT NULL,
    TENLOP NVARCHAR(40)  NOT NULL,

    CONSTRAINT PK_Lop
        PRIMARY KEY (MALOP),

    CONSTRAINT UQ_Lop_TENLOP
        UNIQUE (TENLOP)
);
GO


/* ================================================================
   DB-03
   TẠO BẢNG SINHVIEN

   PHAI:
       1 = Nam
       0 = Nữ

   NGHIHOC:
       0 = Đang học
       1 = Nghỉ học

   Sinh viên bắt buộc phải thuộc một lớp.
   ================================================================ */

CREATE TABLE Sinhvien
(
    MASV      NCHAR(10)       NOT NULL,
    HO        NVARCHAR(40)    NULL,
    TEN       NVARCHAR(10)    NULL,

    MALOP     NCHAR(8)        NOT NULL,

    PHAI      BIT             NOT NULL,

    NGAYSINH  DATETIME        NULL,
    NOISINH   NVARCHAR(40)    NULL,
    DIACHI    NVARCHAR(80)    NULL,

    -- Giữ TEXT để khớp cấu trúc đề bài
    GHICHU    TEXT            NULL,

    NGHIHOC   BIT             NOT NULL,

    HINH      NVARCHAR(1000)  NULL,

    CONSTRAINT PK_Sinhvien
        PRIMARY KEY (MASV)
);
GO


/* ================================================================
   DB-04
   TẠO BẢNG GIANGVIEN

   PHAI:
       1 = Nam
       0 = Nữ
   ================================================================ */

CREATE TABLE Giangvien
(
    MAGV  NCHAR(10)      NOT NULL,
    HO    NVARCHAR(40)   NULL,
    TEN   NVARCHAR(10)   NULL,
    PHAI  BIT            NOT NULL,

    CONSTRAINT PK_Giangvien
        PRIMARY KEY (MAGV)
);
GO


/* ================================================================
   DB-05
   TẠO BẢNG MONHOC

   - MAMH Primary Key
   - TENMH Unique
   - SoTCLT >= 0
   - SoTCTH >= 0
   ================================================================ */

CREATE TABLE Monhoc
(
    MAMH    NCHAR(5)      NOT NULL,
    TENMH   NVARCHAR(40)  NOT NULL,

    SoTCLT  INT           NOT NULL,
    SoTCTH  INT           NOT NULL,

    CONSTRAINT PK_Monhoc
        PRIMARY KEY (MAMH),

    CONSTRAINT UQ_Monhoc_TENMH
        UNIQUE (TENMH),

    CONSTRAINT CK_Monhoc_SoTCLT
        CHECK (SoTCLT >= 0),

    CONSTRAINT CK_Monhoc_SoTCTH
        CHECK (SoTCTH >= 0)
);
GO


/* ================================================================
   DB-06
   TẠO BẢNG DIEM

   Primary Key:
       MASV + MAMH + LAN

   LAN:
       Chỉ được 1 hoặc 2

   DIEM:
       NULL      = Vắng thi
       0 -> 10   = Có điểm

   Không có record tương ứng:
       = Chưa nhập điểm
   ================================================================ */

CREATE TABLE Diem
(
    MASV  NCHAR(10)  NOT NULL,
    MAMH  NCHAR(5)   NOT NULL,

    LAN   SMALLINT    NOT NULL,

    DIEM  FLOAT       NULL,

    CONSTRAINT PK_Diem
        PRIMARY KEY (MASV, MAMH, LAN),

    CONSTRAINT CK_Diem_LAN
        CHECK (LAN >= 1 AND LAN <= 2),

    CONSTRAINT CK_Diem_DIEM
        CHECK
        (
            DIEM IS NULL
            OR
            (DIEM >= 0 AND DIEM <= 10)
        )
);
GO


/* ================================================================
   DB-07
   FOREIGN KEY CONSTRAINTS
   ================================================================ */


/* ------------------------------------------------
   Sinhvien.MALOP
       -> Lop.MALOP
   ------------------------------------------------ */

ALTER TABLE Sinhvien
ADD CONSTRAINT FK_Sinhvien_Lop
    FOREIGN KEY (MALOP)
    REFERENCES Lop(MALOP);
GO


/* ------------------------------------------------
   Diem.MASV
       -> Sinhvien.MASV
   ------------------------------------------------ */

ALTER TABLE Diem
ADD CONSTRAINT FK_Diem_Sinhvien
    FOREIGN KEY (MASV)
    REFERENCES Sinhvien(MASV);
GO


/* ------------------------------------------------
   Diem.MAMH
       -> Monhoc.MAMH
   ------------------------------------------------ */

ALTER TABLE Diem
ADD CONSTRAINT FK_Diem_Monhoc
    FOREIGN KEY (MAMH)
    REFERENCES Monhoc(MAMH);
GO


/* ================================================================
   DB-08
   DEFAULT CONSTRAINTS
   ================================================================ */


/* ------------------------------------------------
   Sinh viên:
   PHAI mặc định = 1 (Nam)
   ------------------------------------------------ */

ALTER TABLE Sinhvien
ADD CONSTRAINT DF_Sinhvien_PHAI
    DEFAULT 1 FOR PHAI;
GO


/* ------------------------------------------------
   Sinh viên:
   NGHIHOC mặc định = 0 (Đang học)
   ------------------------------------------------ */

ALTER TABLE Sinhvien
ADD CONSTRAINT DF_Sinhvien_NGHIHOC
    DEFAULT 0 FOR NGHIHOC;
GO


/* ------------------------------------------------
   Giảng viên:
   PHAI mặc định = 1 (Nam)
   ------------------------------------------------ */

ALTER TABLE Giangvien
ADD CONSTRAINT DF_Giangvien_PHAI
    DEFAULT 1 FOR PHAI;
GO


/* ================================================================
   HOÀN THÀNH DB-01 -> DB-08
   ================================================================ */

PRINT N'=====================================================';
PRINT N'QLDSV - EPIC 1.1';
PRINT N'Đã hoàn thành DB-01 -> DB-08';
PRINT N'DB-09 Seed Data chưa được thực hiện.';
PRINT N'=====================================================';
GO