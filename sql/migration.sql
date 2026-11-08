-- ============================================================
-- migration.sql
-- PetCareDB v0.1 -> v1.0
-- 第6周：规范化与迁移
--
-- 运行前提：
--   1. 已按 sql/01~08 建好 v0.1，并保留样例数据；
--   2. 已备份 PetCareDB（本仓库使用 PetCareDB_v01 作为基线副本）；
--   3. 以 sysadmin/dbo 身份执行本脚本。
--
-- 本脚本做四件事：
--   1. Employee 增加登录字段，供第7-9周 Web 登录使用；
--   2. OrderDetail.subtotal 由“存储的派生属性”改为 PERSISTED 计算列，
--      消除 quantity/unit_price 修改后 subtotal 不一致的更新异常；
--   3. 新增 v_order_header、v_employee_login 视图，重建受影响的两个视图；
--   4. 为主键生成新增 SEQUENCE，并补充常用索引。
--
-- 注意：本脚本不是“删库重建”。它保留 v0.1 的全部业务数据。
-- ============================================================

USE PetCareDB;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    /* ========================================================
       1. Employee 登录字段
       ======================================================== */
    IF COL_LENGTH('dbo.Employee', 'login_name') IS NULL
        ALTER TABLE dbo.Employee ADD login_name VARCHAR(30) NULL;

    IF COL_LENGTH('dbo.Employee', 'password_hash') IS NULL
        ALTER TABLE dbo.Employee ADD password_hash VARCHAR(255) NULL;

    IF COL_LENGTH('dbo.Employee', 'is_active') IS NULL
        ALTER TABLE dbo.Employee
            ADD is_active BIT NOT NULL
                CONSTRAINT DF_Employee_is_active DEFAULT (1);

    -- 样例账号：manager / Manager@123，clerk / Clerk@123
    -- 密码为 werkzeug scrypt 哈希，B 的业务层使用 check_password_hash 校验。
    -- 新列在同一批次中刚加入，SQL Server 编译整批时还看不到，
    -- 因此引用 login_name / password_hash 的语句必须用动态 SQL。
    EXEC sp_executesql N'
        UPDATE dbo.Employee
        SET login_name = CASE
                WHEN employee_id = ''E001'' THEN ''manager''
                WHEN employee_id = ''E002'' THEN ''clerk''
                ELSE LOWER(RTRIM(employee_id))
            END,
            password_hash = CASE
                WHEN employee_id = ''E001'' THEN ''scrypt:32768:8:1$Ki6bw3oSqJzwe2zU$5cf496cde1ca7e4f9307e3e1399b5c499cf86840d4ea3136d54d5a9a06f194e3f60b686b833374e6123cee23c63d6d660270bbb31090f8599e0a379df5080ee8''
                ELSE ''scrypt:32768:8:1$f8nkO3RZhWJuTScQ$d5c807be3baff875bcb01c5147a58dcbe20498b854ee9c7941906faea1b6818d753861c031b8a30e5a2b5459379188a956bc07738216e31af2306bc543fc61de''
            END
        WHERE login_name IS NULL OR password_hash IS NULL;

        UPDATE dbo.Employee
        SET login_name = LOWER(RTRIM(employee_id))
        WHERE login_name IS NULL;

        UPDATE dbo.Employee
        SET password_hash = ''scrypt:32768:8:1$f8nkO3RZhWJuTScQ$d5c807be3baff875bcb01c5147a58dcbe20498b854ee9c7941906faea1b6818d753861c031b8a30e5a2b5459379188a956bc07738216e31af2306bc543fc61de''
        WHERE password_hash IS NULL;

        ALTER TABLE dbo.Employee ALTER COLUMN login_name VARCHAR(30) NOT NULL;
        ALTER TABLE dbo.Employee ALTER COLUMN password_hash VARCHAR(255) NOT NULL;

        IF NOT EXISTS (
            SELECT 1 FROM sys.indexes
            WHERE name = ''UX_Employee_login_name''
              AND object_id = OBJECT_ID(''dbo.Employee'')
        )
            CREATE UNIQUE INDEX UX_Employee_login_name
                ON dbo.Employee(login_name);
    ';

    /* ========================================================
       2. OrderDetail.subtotal：存储列 -> PERSISTED 计算列
       ======================================================== */
    IF COLUMNPROPERTY(OBJECT_ID('dbo.OrderDetail'), 'subtotal', 'IsComputed') = 0
    BEGIN
        -- 视图依赖 subtotal，先删除，事务内会重建
        DROP VIEW IF EXISTS dbo.v_product_sales;
        DROP VIEW IF EXISTS dbo.v_order_detail;

        -- 删除 subtotal 的 DEFAULT 约束（名称由 SQL Server 自动生成）
        DECLARE @df_name sysname;
        SELECT @df_name = dc.name
        FROM sys.default_constraints dc
        JOIN sys.columns c
          ON dc.parent_object_id = c.object_id
         AND dc.parent_column_id = c.column_id
        WHERE dc.parent_object_id = OBJECT_ID('dbo.OrderDetail')
          AND c.name = 'subtotal';

        IF @df_name IS NOT NULL
        BEGIN
            DECLARE @drop_default_sql NVARCHAR(MAX);
            SET @drop_default_sql = N'ALTER TABLE dbo.OrderDetail DROP CONSTRAINT '
                                  + QUOTENAME(@df_name);
            EXEC sp_executesql @drop_default_sql;
        END;

        -- 删除所有依赖 subtotal 的 CHECK（包括自动命名的 subtotal >= 0
        -- 和 CK_OrderDetail_Subtotal）
        DECLARE @ck_name sysname;
        DECLARE @drop_check_sql NVARCHAR(MAX);
        DECLARE subtotal_checks CURSOR LOCAL FAST_FORWARD FOR
            SELECT name
            FROM sys.check_constraints
            WHERE parent_object_id = OBJECT_ID('dbo.OrderDetail')
              AND definition LIKE '%subtotal%';

        OPEN subtotal_checks;
        FETCH NEXT FROM subtotal_checks INTO @ck_name;
        WHILE @@FETCH_STATUS = 0
        BEGIN
            SET @drop_check_sql = N'ALTER TABLE dbo.OrderDetail DROP CONSTRAINT '
                                + QUOTENAME(@ck_name);
            EXEC sp_executesql @drop_check_sql;
            FETCH NEXT FROM subtotal_checks INTO @ck_name;
        END;
        CLOSE subtotal_checks;
        DEALLOCATE subtotal_checks;

        -- DROP 与 ADD 分开执行：同一批次编译时旧列仍然存在，
        -- 放在同一批会报“列名重复”。
        EXEC sp_executesql N'ALTER TABLE dbo.OrderDetail DROP COLUMN subtotal;';
        EXEC sp_executesql N'
            ALTER TABLE dbo.OrderDetail
                ADD subtotal AS CAST(quantity * unit_price AS DECIMAL(10, 2)) PERSISTED;
        ';
    END;

    /* ========================================================
       3. 视图：重建受影响的两个视图，新增两个 v1.0 视图
       ======================================================== */
    EXEC(N'
        CREATE OR ALTER VIEW dbo.v_order_detail AS
        SELECT RTRIM(o.order_id) AS order_id, o.order_time, o.pay_method, o.order_status,
               ISNULL(m.member_name, ''散客'') AS member_name,
               e.employee_name,
               p.product_name, d.quantity, d.unit_price, d.subtotal
        FROM dbo.Orders o
        JOIN dbo.OrderDetail d ON o.order_id = d.order_id
        JOIN dbo.Product p     ON d.product_id = p.product_id
        JOIN dbo.Employee e    ON o.employee_id = e.employee_id
        LEFT JOIN dbo.Member m ON o.member_id = m.member_id;
    ');

    EXEC(N'
        CREATE OR ALTER VIEW dbo.v_product_sales AS
        SELECT RTRIM(p.product_id) AS product_id, p.product_name, p.category, p.price,
               ISNULL(SUM(d.quantity), 0) AS sold_qty,
               ISNULL(SUM(d.subtotal), 0) AS sales_amount
        FROM dbo.Product p
        LEFT JOIN dbo.OrderDetail d ON p.product_id = d.product_id
        GROUP BY p.product_id, p.product_name, p.category, p.price;
    ');

    EXEC(N'
        CREATE OR ALTER VIEW dbo.v_order_header AS
        SELECT RTRIM(o.order_id) AS order_id,
               RTRIM(o.member_id) AS member_id,
               ISNULL(m.member_name, ''散客'') AS member_name,
               RTRIM(o.employee_id) AS employee_id,
               e.employee_name,
               o.order_type, o.order_time, o.total_amount,
               o.pay_method, o.order_status
        FROM dbo.Orders o
        JOIN dbo.Employee e    ON o.employee_id = e.employee_id
        LEFT JOIN dbo.Member m ON o.member_id = m.member_id;
    ');

    EXEC(N'
        CREATE OR ALTER VIEW dbo.v_employee_login AS
        SELECT RTRIM(employee_id) AS employee_id,
               employee_name,
               login_name,
               password_hash,
               role,
               is_active
        FROM dbo.Employee;
    ');

    /* ========================================================
       4. 主键生成 SEQUENCE
       ======================================================== */
    IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = 'SEQ_Product' AND schema_id = SCHEMA_ID('dbo'))
        CREATE SEQUENCE dbo.SEQ_Product AS INT START WITH 1001 INCREMENT BY 1;

    IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = 'SEQ_Inventory' AND schema_id = SCHEMA_ID('dbo'))
        CREATE SEQUENCE dbo.SEQ_Inventory AS INT START WITH 1001 INCREMENT BY 1;

    IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = 'SEQ_InventoryLog' AND schema_id = SCHEMA_ID('dbo'))
        CREATE SEQUENCE dbo.SEQ_InventoryLog AS INT START WITH 1001 INCREMENT BY 1;

    IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = 'SEQ_Member' AND schema_id = SCHEMA_ID('dbo'))
        CREATE SEQUENCE dbo.SEQ_Member AS INT START WITH 1001 INCREMENT BY 1;

    IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = 'SEQ_Employee' AND schema_id = SCHEMA_ID('dbo'))
        CREATE SEQUENCE dbo.SEQ_Employee AS INT START WITH 1001 INCREMENT BY 1;

    IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = 'SEQ_Order' AND schema_id = SCHEMA_ID('dbo'))
        CREATE SEQUENCE dbo.SEQ_Order AS INT START WITH 1001 INCREMENT BY 1;

    IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = 'SEQ_OrderDetail' AND schema_id = SCHEMA_ID('dbo'))
        CREATE SEQUENCE dbo.SEQ_OrderDetail AS INT START WITH 1001 INCREMENT BY 1;

    IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = 'SEQ_PetService' AND schema_id = SCHEMA_ID('dbo'))
        CREATE SEQUENCE dbo.SEQ_PetService AS INT START WITH 1001 INCREMENT BY 1;

    IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = 'SEQ_ServiceAppointment' AND schema_id = SCHEMA_ID('dbo'))
        CREATE SEQUENCE dbo.SEQ_ServiceAppointment AS INT START WITH 1001 INCREMENT BY 1;

    /* ========================================================
       5. 常用索引
       ======================================================== */
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Orders_OrderTime' AND object_id = OBJECT_ID('dbo.Orders'))
        CREATE INDEX IX_Orders_OrderTime ON dbo.Orders(order_time);

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Orders_MemberID' AND object_id = OBJECT_ID('dbo.Orders'))
        CREATE INDEX IX_Orders_MemberID ON dbo.Orders(member_id);

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Orders_EmployeeID' AND object_id = OBJECT_ID('dbo.Orders'))
        CREATE INDEX IX_Orders_EmployeeID ON dbo.Orders(employee_id);

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_OrderDetail_OrderID' AND object_id = OBJECT_ID('dbo.OrderDetail'))
        CREATE INDEX IX_OrderDetail_OrderID ON dbo.OrderDetail(order_id);

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_OrderDetail_ProductID' AND object_id = OBJECT_ID('dbo.OrderDetail'))
        CREATE INDEX IX_OrderDetail_ProductID ON dbo.OrderDetail(product_id);

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_InventoryLog_ProductTime' AND object_id = OBJECT_ID('dbo.InventoryLog'))
        CREATE INDEX IX_InventoryLog_ProductTime ON dbo.InventoryLog(product_id, change_time);

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ServiceAppointment_Time' AND object_id = OBJECT_ID('dbo.ServiceAppointment'))
        CREATE INDEX IX_ServiceAppointment_Time ON dbo.ServiceAppointment(appoint_time);

    /* ========================================================
       6. 迁移版本记录
       ======================================================== */
    IF OBJECT_ID('dbo.SchemaVersion', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.SchemaVersion (
            version     VARCHAR(20)   NOT NULL PRIMARY KEY,
            applied_at  DATETIME2(0)  NOT NULL CONSTRAINT DF_SchemaVersion_applied_at DEFAULT SYSDATETIME(),
            description NVARCHAR(200) NULL
        );
    END;

    IF NOT EXISTS (SELECT 1 FROM dbo.SchemaVersion WHERE version = 'v1.0')
        INSERT INTO dbo.SchemaVersion (version, description)
        VALUES ('v1.0', N'第5-6周：登录字段、计算列 subtotal、视图、序列、索引');

    COMMIT TRANSACTION;
    PRINT 'PetCareDB migration v0.1 -> v1.0 completed.';
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0
        ROLLBACK TRANSACTION;

    PRINT 'Migration failed: ' + ERROR_MESSAGE();
    THROW;
END CATCH;
GO
