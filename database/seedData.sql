/* ================================================================
   PROJECT  : QUẢN LÝ ĐIỂM SINH VIÊN
   DATABASE : QLDSV
   EPIC 1.1
   TASK     : DB-09 - SEED DATA

   Yêu cầu:
   - Chạy sau DB-01 -> DB-08
   - Có dữ liệu mẫu:
       + Lop
       + Sinhvien
       + Giangvien
       + Monhoc
       + Diem

   Quy ước điểm:
   ---------------------------------------------------------------
   Không có record trong Diem
       => Chưa nhập điểm

   Có record, DIEM IS NULL
       => Vắng thi

   Có record, DIEM từ 0 đến 10
       => Có điểm
   ================================================================ */

USE QLDSV;
GO

SET NOCOUNT ON;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    /* ============================================================
       1. SEED LOP
       ============================================================ */

    IF NOT EXISTS (
        SELECT 1
        FROM Lop
        WHERE MALOP = N'CNTT01'
    )
    BEGIN
        INSERT INTO Lop (MALOP, TENLOP)
        VALUES (N'CNTT01', N'Công nghệ thông tin 1');
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Lop
        WHERE MALOP = N'CNTT02'
    )
    BEGIN
        INSERT INTO Lop (MALOP, TENLOP)
        VALUES (N'CNTT02', N'Công nghệ thông tin 2');
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Lop
        WHERE MALOP = N'QTKD01'
    )
    BEGIN
        INSERT INTO Lop (MALOP, TENLOP)
        VALUES (N'QTKD01', N'Quản trị kinh doanh 1');
    END;


    /* ============================================================
       2. SEED GIANGVIEN
       ============================================================ */

    IF NOT EXISTS (
        SELECT 1
        FROM Giangvien
        WHERE MAGV = N'GV00000001'
    )
    BEGIN
        INSERT INTO Giangvien
        (
            MAGV,
            HO,
            TEN,
            PHAI
        )
        VALUES
        (
            N'GV00000001',
            N'Nguyễn Văn',
            N'An',
            1
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Giangvien
        WHERE MAGV = N'GV00000002'
    )
    BEGIN
        INSERT INTO Giangvien
        (
            MAGV,
            HO,
            TEN,
            PHAI
        )
        VALUES
        (
            N'GV00000002',
            N'Trần Thị',
            N'Bình',
            0
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Giangvien
        WHERE MAGV = N'GV00000003'
    )
    BEGIN
        INSERT INTO Giangvien
        (
            MAGV,
            HO,
            TEN,
            PHAI
        )
        VALUES
        (
            N'GV00000003',
            N'Lê Hoàng',
            N'Minh',
            1
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Giangvien
        WHERE MAGV = N'GV00000004'
    )
    BEGIN
        INSERT INTO Giangvien
        (
            MAGV,
            HO,
            TEN,
            PHAI
        )
        VALUES
        (
            N'GV00000004',
            N'Phạm Thị',
            N'Lan',
            0
        );
    END;


    /* ============================================================
       3. SEED MONHOC
       ============================================================ */

    IF NOT EXISTS (
        SELECT 1
        FROM Monhoc
        WHERE MAMH = N'CSDL1'
    )
    BEGIN
        INSERT INTO Monhoc
        (
            MAMH,
            TENMH,
            SoTCLT,
            SoTCTH
        )
        VALUES
        (
            N'CSDL1',
            N'Cơ sở dữ liệu',
            3,
            1
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Monhoc
        WHERE MAMH = N'CTDL1'
    )
    BEGIN
        INSERT INTO Monhoc
        (
            MAMH,
            TENMH,
            SoTCLT,
            SoTCTH
        )
        VALUES
        (
            N'CTDL1',
            N'Cấu trúc dữ liệu',
            3,
            1
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Monhoc
        WHERE MAMH = N'LTHDT'
    )
    BEGIN
        INSERT INTO Monhoc
        (
            MAMH,
            TENMH,
            SoTCLT,
            SoTCTH
        )
        VALUES
        (
            N'LTHDT',
            N'Lập trình hướng đối tượng',
            3,
            1
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Monhoc
        WHERE MAMH = N'MMT01'
    )
    BEGIN
        INSERT INTO Monhoc
        (
            MAMH,
            TENMH,
            SoTCLT,
            SoTCTH
        )
        VALUES
        (
            N'MMT01',
            N'Mạng máy tính',
            3,
            1
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Monhoc
        WHERE MAMH = N'KTL01'
    )
    BEGIN
        INSERT INTO Monhoc
        (
            MAMH,
            TENMH,
            SoTCLT,
            SoTCTH
        )
        VALUES
        (
            N'KTL01',
            N'Kinh tế lượng',
            3,
            0
        );
    END;


    /* ============================================================
       4. SEED SINHVIEN
       ============================================================ */


    -- ------------------------------------------------------------
    -- Lớp CNTT01
    -- ------------------------------------------------------------

    IF NOT EXISTS (
        SELECT 1
        FROM Sinhvien
        WHERE MASV = N'SV00000001'
    )
    BEGIN
        INSERT INTO Sinhvien
        (
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
        )
        VALUES
        (
            N'SV00000001',
            N'Nguyễn Văn',
            N'Nam',
            N'CNTT01',
            1,
            '2004-01-15',
            N'TP. Hồ Chí Minh',
            N'Quận 1, TP. Hồ Chí Minh',
            NULL,
            0,
            NULL
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Sinhvien
        WHERE MASV = N'SV00000002'
    )
    BEGIN
        INSERT INTO Sinhvien
        (
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
        )
        VALUES
        (
            N'SV00000002',
            N'Trần Thị',
            N'Mai',
            N'CNTT01',
            0,
            '2004-03-20',
            N'Đồng Nai',
            N'Biên Hòa, Đồng Nai',
            NULL,
            0,
            NULL
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Sinhvien
        WHERE MASV = N'SV00000003'
    )
    BEGIN
        INSERT INTO Sinhvien
        (
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
        )
        VALUES
        (
            N'SV00000003',
            N'Lê Minh',
            N'Khoa',
            N'CNTT01',
            1,
            '2004-07-08',
            N'Bình Dương',
            N'Thủ Dầu Một, Bình Dương',
            NULL,
            0,
            NULL
        );
    END;


    -- Sinh viên nghỉ học để test rule NGHIHOC = 0
    IF NOT EXISTS (
        SELECT 1
        FROM Sinhvien
        WHERE MASV = N'SV00000004'
    )
    BEGIN
        INSERT INTO Sinhvien
        (
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
        )
        VALUES
        (
            N'SV00000004',
            N'Phạm Quốc',
            N'Bảo',
            N'CNTT01',
            1,
            '2004-05-12',
            N'Tây Ninh',
            N'Tây Ninh',
            NULL,
            1,
            NULL
        );
    END;


    -- ------------------------------------------------------------
    -- Lớp CNTT02
    -- ------------------------------------------------------------

    IF NOT EXISTS (
        SELECT 1
        FROM Sinhvien
        WHERE MASV = N'SV00000005'
    )
    BEGIN
        INSERT INTO Sinhvien
        (
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
        )
        VALUES
        (
            N'SV00000005',
            N'Võ Hoàng',
            N'Long',
            N'CNTT02',
            1,
            '2004-09-11',
            N'Long An',
            N'Tân An, Long An',
            NULL,
            0,
            NULL
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Sinhvien
        WHERE MASV = N'SV00000006'
    )
    BEGIN
        INSERT INTO Sinhvien
        (
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
        )
        VALUES
        (
            N'SV00000006',
            N'Đặng Thị',
            N'Hương',
            N'CNTT02',
            0,
            '2004-11-25',
            N'Bến Tre',
            N'Bến Tre',
            NULL,
            0,
            NULL
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Sinhvien
        WHERE MASV = N'SV00000007'
    )
    BEGIN
        INSERT INTO Sinhvien
        (
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
        )
        VALUES
        (
            N'SV00000007',
            N'Bùi Gia',
            N'Huy',
            N'CNTT02',
            1,
            '2004-06-30',
            N'TP. Hồ Chí Minh',
            N'Thủ Đức, TP. Hồ Chí Minh',
            NULL,
            0,
            NULL
        );
    END;


    -- ------------------------------------------------------------
    -- Lớp QTKD01
    -- ------------------------------------------------------------

    IF NOT EXISTS (
        SELECT 1
        FROM Sinhvien
        WHERE MASV = N'SV00000008'
    )
    BEGIN
        INSERT INTO Sinhvien
        (
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
        )
        VALUES
        (
            N'SV00000008',
            N'Nguyễn Thị',
            N'Linh',
            N'QTKD01',
            0,
            '2004-02-18',
            N'Tiền Giang',
            N'Mỹ Tho, Tiền Giang',
            NULL,
            0,
            NULL
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Sinhvien
        WHERE MASV = N'SV00000009'
    )
    BEGIN
        INSERT INTO Sinhvien
        (
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
        )
        VALUES
        (
            N'SV00000009',
            N'Hoàng Anh',
            N'Tú',
            N'QTKD01',
            1,
            '2004-08-14',
            N'Vĩnh Long',
            N'Vĩnh Long',
            NULL,
            0,
            NULL
        );
    END;


    /* ============================================================
       5. SEED DIEM
       ============================================================

       Các case test:

       SV00000001:
       - CSDL1 lần 1 = 8.0
       => Đạt ngay lần 1

       SV00000002:
       - CSDL1 lần 1 = 4.0
       - CSDL1 lần 2 = 7.0
       => Rớt lần 1, đạt lần 2

       SV00000003:
       - CSDL1 lần 1 = NULL
       - CSDL1 lần 2 = 6.0
       => Vắng lần 1, thi lần 2

       SV00000005:
       - Không có record CSDL1
       => Chưa nhập điểm CSDL1

       SV00000006:
       - CSDL1 lần 1 = 4.5
       => Rớt lần 1, chưa nhập lần 2
       ============================================================ */


    /* ------------------------------------------------------------
       SV00000001
       Đạt lần 1
       ------------------------------------------------------------ */

    IF NOT EXISTS (
        SELECT 1
        FROM Diem
        WHERE MASV = N'SV00000001'
          AND MAMH = N'CSDL1'
          AND LAN = 1
    )
    BEGIN
        INSERT INTO Diem
        (
            MASV,
            MAMH,
            LAN,
            DIEM
        )
        VALUES
        (
            N'SV00000001',
            N'CSDL1',
            1,
            8.0
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Diem
        WHERE MASV = N'SV00000001'
          AND MAMH = N'CTDL1'
          AND LAN = 1
    )
    BEGIN
        INSERT INTO Diem
        (
            MASV,
            MAMH,
            LAN,
            DIEM
        )
        VALUES
        (
            N'SV00000001',
            N'CTDL1',
            1,
            6.5
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Diem
        WHERE MASV = N'SV00000001'
          AND MAMH = N'LTHDT'
          AND LAN = 1
    )
    BEGIN
        INSERT INTO Diem
        (
            MASV,
            MAMH,
            LAN,
            DIEM
        )
        VALUES
        (
            N'SV00000001',
            N'LTHDT',
            1,
            9.0
        );
    END;


    /* ------------------------------------------------------------
       SV00000002
       Rớt lần 1 -> đạt lần 2
       ------------------------------------------------------------ */

    IF NOT EXISTS (
        SELECT 1
        FROM Diem
        WHERE MASV = N'SV00000002'
          AND MAMH = N'CSDL1'
          AND LAN = 1
    )
    BEGIN
        INSERT INTO Diem
        (
            MASV,
            MAMH,
            LAN,
            DIEM
        )
        VALUES
        (
            N'SV00000002',
            N'CSDL1',
            1,
            4.0
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Diem
        WHERE MASV = N'SV00000002'
          AND MAMH = N'CSDL1'
          AND LAN = 2
    )
    BEGIN
        INSERT INTO Diem
        (
            MASV,
            MAMH,
            LAN,
            DIEM
        )
        VALUES
        (
            N'SV00000002',
            N'CSDL1',
            2,
            7.0
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Diem
        WHERE MASV = N'SV00000002'
          AND MAMH = N'CTDL1'
          AND LAN = 1
    )
    BEGIN
        INSERT INTO Diem
        (
            MASV,
            MAMH,
            LAN,
            DIEM
        )
        VALUES
        (
            N'SV00000002',
            N'CTDL1',
            1,
            2.0
        );
    END;


    /* ------------------------------------------------------------
       SV00000003
       Vắng lần 1 -> thi lần 2
       ------------------------------------------------------------ */

    IF NOT EXISTS (
        SELECT 1
        FROM Diem
        WHERE MASV = N'SV00000003'
          AND MAMH = N'CSDL1'
          AND LAN = 1
    )
    BEGIN
        INSERT INTO Diem
        (
            MASV,
            MAMH,
            LAN,
            DIEM
        )
        VALUES
        (
            N'SV00000003',
            N'CSDL1',
            1,
            NULL
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Diem
        WHERE MASV = N'SV00000003'
          AND MAMH = N'CSDL1'
          AND LAN = 2
    )
    BEGIN
        INSERT INTO Diem
        (
            MASV,
            MAMH,
            LAN,
            DIEM
        )
        VALUES
        (
            N'SV00000003',
            N'CSDL1',
            2,
            6.0
        );
    END;


    /* ------------------------------------------------------------
       CNTT02
       ------------------------------------------------------------ */

    IF NOT EXISTS (
        SELECT 1
        FROM Diem
        WHERE MASV = N'SV00000005'
          AND MAMH = N'CTDL1'
          AND LAN = 1
    )
    BEGIN
        INSERT INTO Diem
        (
            MASV,
            MAMH,
            LAN,
            DIEM
        )
        VALUES
        (
            N'SV00000005',
            N'CTDL1',
            1,
            9.0
        );
    END;


    -- CSDL1 của SV00000005 cố ý KHÔNG INSERT.
    -- Điều này biểu diễn: chưa nhập điểm.


    IF NOT EXISTS (
        SELECT 1
        FROM Diem
        WHERE MASV = N'SV00000006'
          AND MAMH = N'CSDL1'
          AND LAN = 1
    )
    BEGIN
        INSERT INTO Diem
        (
            MASV,
            MAMH,
            LAN,
            DIEM
        )
        VALUES
        (
            N'SV00000006',
            N'CSDL1',
            1,
            4.5
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Diem
        WHERE MASV = N'SV00000006'
          AND MAMH = N'CTDL1'
          AND LAN = 1
    )
    BEGIN
        INSERT INTO Diem
        (
            MASV,
            MAMH,
            LAN,
            DIEM
        )
        VALUES
        (
            N'SV00000006',
            N'CTDL1',
            1,
            7.5
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Diem
        WHERE MASV = N'SV00000007'
          AND MAMH = N'CSDL1'
          AND LAN = 1
    )
    BEGIN
        INSERT INTO Diem
        (
            MASV,
            MAMH,
            LAN,
            DIEM
        )
        VALUES
        (
            N'SV00000007',
            N'CSDL1',
            1,
            5.0
        );
    END;


    /* ------------------------------------------------------------
       QTKD01
       ------------------------------------------------------------ */

    IF NOT EXISTS (
        SELECT 1
        FROM Diem
        WHERE MASV = N'SV00000008'
          AND MAMH = N'KTL01'
          AND LAN = 1
    )
    BEGIN
        INSERT INTO Diem
        (
            MASV,
            MAMH,
            LAN,
            DIEM
        )
        VALUES
        (
            N'SV00000008',
            N'KTL01',
            1,
            8.5
        );
    END;


    IF NOT EXISTS (
        SELECT 1
        FROM Diem
        WHERE MASV = N'SV00000009'
          AND MAMH = N'KTL01'
          AND LAN = 1
    )
    BEGIN
        INSERT INTO Diem
        (
            MASV,
            MAMH,
            LAN,
            DIEM
        )
        VALUES
        (
            N'SV00000009',
            N'KTL01',
            1,
            3.5
        );
    END;


    COMMIT TRANSACTION;

    PRINT N'=====================================================';
    PRINT N'DB-09 SEED DATA THÀNH CÔNG';
    PRINT N'=====================================================';

END TRY
BEGIN CATCH

    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    PRINT N'=====================================================';
    PRINT N'DB-09 SEED DATA THẤT BẠI';
    PRINT N'=====================================================';

    THROW;

END CATCH;
GO