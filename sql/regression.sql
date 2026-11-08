-- ============================================================
-- regression.sql
-- PetCareDB v1.0 迁移后回归测试
--
-- 运行顺序：sql/migration.sql -> sql/09_app_accounts.sql -> 本脚本
-- 运行身份：sysadmin/dbo
--
-- 说明：
--   1. 本脚本同时校验“数据语义是否保持”和“权限边界是否生效”；
--   2. 所有写操作都在事务中回滚，不改变样例数据；
--   3. 任一断言失败会 THROW，脚本以非零状态结束。
-- ============================================================

USE PetCareDB;
GO

SET NOCOUNT ON;
GO

PRINT '--- 1. 迁移结构检查 ---';

IF COL_LENGTH('dbo.Employee', 'login_name') IS NULL
    THROW 51001, 'Employee.login_name is missing', 1;

IF COL_LENGTH('dbo.Employee', 'password_hash') IS NULL
    THROW 51002, 'Employee.password_hash is missing', 1;

IF COL_LENGTH('dbo.Employee', 'is_active') IS NULL
    THROW 51003, 'Employee.is_active is missing', 1;

IF COLUMNPROPERTY(OBJECT_ID('dbo.OrderDetail'), 'subtotal', 'IsComputed') <> 1
    THROW 51004, 'OrderDetail.subtotal is not a computed column', 1;

IF OBJECT_ID('dbo.v_order_header', 'V') IS NULL
    THROW 51005, 'v_order_header is missing', 1;

IF OBJECT_ID('dbo.v_employee_login', 'V') IS NULL
    THROW 51006, 'v_employee_login is missing', 1;

IF (SELECT COUNT(*) FROM sys.sequences
    WHERE name IN ('SEQ_Product','SEQ_Inventory','SEQ_InventoryLog','SEQ_Member',
                   'SEQ_Employee','SEQ_Order','SEQ_OrderDetail','SEQ_PetService',
                   'SEQ_ServiceAppointment')) <> 9
    THROW 51007, 'Some ID sequences are missing', 1;

PRINT 'PASS: structure';

PRINT '--- 2. 迁移前后数据量保持 ---';

IF (SELECT COUNT(*) FROM dbo.Product) <> 3
    THROW 51010, 'Product row count changed', 1;
IF (SELECT COUNT(*) FROM dbo.Inventory) <> 3
    THROW 51011, 'Inventory row count changed', 1;
IF (SELECT COUNT(*) FROM dbo.InventoryLog) <> 3
    THROW 51012, 'InventoryLog row count changed', 1;
IF (SELECT COUNT(*) FROM dbo.Member) <> 2
    THROW 51013, 'Member row count changed', 1;
IF (SELECT COUNT(*) FROM dbo.Employee) <> 2
    THROW 51014, 'Employee row count changed', 1;
IF (SELECT COUNT(*) FROM dbo.Orders) <> 2
    THROW 51015, 'Orders row count changed', 1;
IF (SELECT COUNT(*) FROM dbo.OrderDetail) <> 2
    THROW 51016, 'OrderDetail row count changed', 1;
IF (SELECT COUNT(*) FROM dbo.PetService) <> 3
    THROW 51017, 'PetService row count changed', 1;
IF (SELECT COUNT(*) FROM dbo.ServiceAppointment) <> 2
    THROW 51018, 'ServiceAppointment row count changed', 1;

PRINT 'PASS: row counts';

PRINT '--- 3. 订单金额与计算列 ---';

IF EXISTS (
    SELECT 1 FROM dbo.OrderDetail
    WHERE subtotal <> CAST(quantity * unit_price AS DECIMAL(10, 2))
)
    THROW 51020, 'Computed subtotal does not match quantity * unit_price', 1;

IF EXISTS (
    SELECT 1
    FROM dbo.Orders o
    OUTER APPLY (
        SELECT ISNULL(SUM(d.subtotal), 0) AS detail_total
        FROM dbo.OrderDetail d
        WHERE d.order_id = o.order_id
    ) x
    WHERE o.total_amount <> x.detail_total
)
    THROW 51021, 'Orders.total_amount does not match sum of details', 1;

IF (SELECT COUNT(*) FROM dbo.v_order_detail) <> 2
    THROW 51022, 'v_order_detail row count unexpected', 1;

IF (SELECT SUM(subtotal) FROM dbo.v_order_detail) <> 147.90
    THROW 51023, 'v_order_detail total amount unexpected', 1;

PRINT 'PASS: order amounts';

PRINT '--- 4. 统计视图回归 ---';

IF (SELECT sold_qty FROM dbo.v_product_sales WHERE product_id = 'P001') <> 1
    THROW 51030, 'P001 sold_qty changed', 1;
IF (SELECT sales_amount FROM dbo.v_product_sales WHERE product_id = 'P001') <> 128.00
    THROW 51031, 'P001 sales_amount changed', 1;
IF (SELECT sold_qty FROM dbo.v_product_sales WHERE product_id = 'P002') <> 1
    THROW 51032, 'P002 sold_qty changed', 1;
IF (SELECT sales_amount FROM dbo.v_product_sales WHERE product_id = 'P002') <> 19.90
    THROW 51033, 'P002 sales_amount changed', 1;
IF (SELECT sold_qty FROM dbo.v_product_sales WHERE product_id = 'P003') <> 0
    THROW 51034, 'P003 sold_qty changed', 1;

IF (SELECT COUNT(*) FROM dbo.v_inventory_status) <> 3
    THROW 51035, 'v_inventory_status row count changed', 1;
IF EXISTS (SELECT 1 FROM dbo.v_inventory_status WHERE stock_status <> '正常')
    THROW 51036, 'v_inventory_status status changed', 1;

IF (SELECT order_count FROM dbo.v_member_consumption WHERE member_id = 'M001') <> 1
    THROW 51037, 'M001 order_count changed', 1;
IF (SELECT total_spent FROM dbo.v_member_consumption WHERE member_id = 'M001') <> 128.00
    THROW 51038, 'M001 total_spent changed', 1;
IF (SELECT order_count FROM dbo.v_member_consumption WHERE member_id = 'M002') <> 0
    THROW 51039, 'M002 order_count changed', 1;

IF (SELECT COUNT(*) FROM dbo.v_service_appointment) <> 2
    THROW 51040, 'v_service_appointment row count changed', 1;

PRINT 'PASS: reporting views';

PRINT '--- 5. 登录视图 ---';

IF (SELECT COUNT(*) FROM dbo.v_employee_login) <> 2
    THROW 51050, 'v_employee_login row count unexpected', 1;

IF NOT EXISTS (
    SELECT 1 FROM dbo.v_employee_login
    WHERE login_name = 'manager' AND role = '店长' AND is_active = 1
)
    THROW 51051, 'manager login account is missing', 1;

IF NOT EXISTS (
    SELECT 1 FROM dbo.v_employee_login
    WHERE login_name = 'clerk' AND role = '店员' AND is_active = 1
)
    THROW 51052, 'clerk login account is missing', 1;

PRINT 'PASS: login view';

PRINT '--- 6. 店员权限 ---';

DECLARE @ok BIT;

-- 6.1 店员可以查询商品、库存
SET @ok = 0;
EXECUTE AS USER = 'clerk_user';
BEGIN TRY
    IF (SELECT COUNT(*) FROM dbo.Product) = 3
       AND (SELECT COUNT(*) FROM dbo.Inventory) = 3
        SET @ok = 1;
END TRY
BEGIN CATCH
    SET @ok = 0;
END CATCH;
REVERT;
IF @ok = 0
    THROW 51060, 'clerk cannot read product/inventory', 1;

-- 6.2 店员可以扣库存（v1.0 新增的 UPDATE 权限）
SET @ok = 0;
EXECUTE AS USER = 'clerk_user';
BEGIN TRY
    BEGIN TRANSACTION;
    UPDATE dbo.Inventory SET quantity = quantity WHERE product_id = 'P001';
    SET @ok = 1;
    ROLLBACK TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    SET @ok = 0;
END CATCH;
REVERT;
IF @ok = 0
    THROW 51061, 'clerk cannot update inventory', 1;

-- 6.3 店员可以通过视图看到订单员工姓名
SET @ok = 0;
EXECUTE AS USER = 'clerk_user';
BEGIN TRY
    IF (SELECT COUNT(*) FROM dbo.v_order_header) = 2
       AND (SELECT COUNT(*) FROM dbo.v_order_detail) = 2
        SET @ok = 1;
END TRY
BEGIN CATCH
    SET @ok = 0;
END CATCH;
REVERT;
IF @ok = 0
    THROW 51062, 'clerk cannot read order views', 1;

-- 6.4 店员不能查看 Employee 基表（预期失败）
SET @ok = 0;
EXECUTE AS USER = 'clerk_user';
BEGIN TRY
    EXEC('SELECT COUNT(*) FROM dbo.Employee');
END TRY
BEGIN CATCH
    IF ERROR_NUMBER() = 229 SET @ok = 1;
END CATCH;
REVERT;
IF @ok = 0
    THROW 51063, 'clerk unexpectedly can read Employee', 1;

-- 6.5 店员不能删除商品（预期失败）
SET @ok = 0;
EXECUTE AS USER = 'clerk_user';
BEGIN TRY
    EXEC('DELETE FROM dbo.Product WHERE product_id = ''P001''');
END TRY
BEGIN CATCH
    IF ERROR_NUMBER() = 229 SET @ok = 1;
END CATCH;
REVERT;
IF @ok = 0
    THROW 51064, 'clerk unexpectedly can delete Product', 1;

PRINT 'PASS: clerk permissions';

PRINT '--- 7. 店长权限 ---';

SET @ok = 0;
EXECUTE AS USER = 'manager_user';
BEGIN TRY
    IF (SELECT COUNT(*) FROM dbo.Employee) = 2
       AND (SELECT COUNT(*) FROM dbo.v_order_header) = 2
        SET @ok = 1;
END TRY
BEGIN CATCH
    SET @ok = 0;
END CATCH;
REVERT;
IF @ok = 0
    THROW 51070, 'manager cannot read Employee/order view', 1;

PRINT 'PASS: manager permissions';

PRINT '--- 8. auth 账号权限 ---';

SET @ok = 0;
EXECUTE AS USER = 'petcare_auth';
BEGIN TRY
    IF (SELECT COUNT(*) FROM dbo.v_employee_login) = 2
        SET @ok = 1;
END TRY
BEGIN CATCH
    SET @ok = 0;
END CATCH;
REVERT;
IF @ok = 0
    THROW 51080, 'auth account cannot read v_employee_login', 1;

SET @ok = 0;
EXECUTE AS USER = 'petcare_auth';
BEGIN TRY
    EXEC('SELECT COUNT(*) FROM dbo.Product');
END TRY
BEGIN CATCH
    IF ERROR_NUMBER() = 229 SET @ok = 1;
END CATCH;
REVERT;
IF @ok = 0
    THROW 51081, 'auth account unexpectedly can read Product', 1;

PRINT 'PASS: auth permissions';

PRINT '--- 9. 下单事务回滚 ---';

DECLARE @before_qty INT = (SELECT quantity FROM dbo.Inventory WHERE product_id = 'P001');
DECLARE @test_order CHAR(12) = 'OTEST000001';
DECLARE @test_detail CHAR(10) = 'DTEST00001';
DECLARE @test_log CHAR(10) = 'LTEST00001';

BEGIN TRY
    BEGIN TRANSACTION;

    INSERT INTO dbo.Orders
        (order_id, member_id, employee_id, order_type, total_amount, pay_method, order_status)
    VALUES
        (@test_order, 'M001', 'E002', '商品', 128.00, '现金', '已完成');

    INSERT INTO dbo.OrderDetail
        (detail_id, order_id, product_id, quantity, unit_price)
    VALUES
        (@test_detail, @test_order, 'P001', 1, 128.00);

    UPDATE dbo.Inventory
    SET quantity = quantity - 1, update_time = GETDATE()
    WHERE product_id = 'P001';

    INSERT INTO dbo.InventoryLog
        (log_id, product_id, change_type, change_qty, remark)
    VALUES
        (@test_log, 'P001', '销售', -1, 'regression rollback test');

    ROLLBACK TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;

IF (SELECT quantity FROM dbo.Inventory WHERE product_id = 'P001') <> @before_qty
    THROW 51090, 'Inventory rollback failed', 1;

IF EXISTS (SELECT 1 FROM dbo.Orders WHERE order_id = @test_order)
    THROW 51091, 'Order rollback failed', 1;

IF EXISTS (SELECT 1 FROM dbo.OrderDetail WHERE detail_id = @test_detail)
    THROW 51092, 'OrderDetail rollback failed', 1;

IF EXISTS (SELECT 1 FROM dbo.InventoryLog WHERE log_id = @test_log)
    THROW 51093, 'InventoryLog rollback failed', 1;

PRINT 'PASS: transaction rollback';

PRINT 'REGRESSION PASS';
GO
