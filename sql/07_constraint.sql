-- 07_constraint.sql
-- PetCare 宠物店管理系统
-- 功能：补充完整性约束并验证（第4周）
--
-- 说明：第3周建表时已定义主码、外码、部分 UNIQUE（Inventory.product_id、
--      Member.phone、Employee.phone）、DEFAULT 和 NOT NULL。本周补充：
--      1. 第2周设计文档中列出但尚未落到数据库的候选码 UNIQUE 约束；
--      2. 需要跨字段维护的业务规则 CHECK 约束。

USE PetCareDB;
GO

-- ============================================================
-- 一、补充完整性约束
-- ============================================================

-- 1. Product 候选码：商品名称 + 类别 唯一（第2周设计文档）
ALTER TABLE Product
    ADD CONSTRAINT UQ_Product_NameCategory UNIQUE (product_name, category);
GO

-- 2. PetService 候选码：服务名称 唯一（第2周设计文档）
ALTER TABLE PetService
    ADD CONSTRAINT UQ_PetService_Name UNIQUE (service_name);
GO

-- 3. OrderDetail 业务规则：小计 = 数量 × 成交单价
ALTER TABLE OrderDetail
    ADD CONSTRAINT CK_OrderDetail_Subtotal CHECK (subtotal = quantity * unit_price);
GO

-- 4. InventoryLog 业务规则：入库数量为正数、销售数量为负数
ALTER TABLE InventoryLog
    ADD CONSTRAINT CK_InventoryLog_Sign
        CHECK ((change_type = '入库' AND change_qty > 0)
            OR (change_type = '销售' AND change_qty < 0));
GO

-- 5. PetService 业务规则：预计时长必须为正数
ALTER TABLE PetService
    ADD CONSTRAINT CK_PetService_Duration CHECK (duration_min IS NULL OR duration_min > 0);
GO

-- ============================================================
-- 二、验证：合法数据（应成功）
-- ============================================================

-- 1. 新增合法商品与库存（商品名称 + 类别未重复，入库数量为正）
INSERT INTO Product (product_id, product_name, category, price, stock_warn, status)
VALUES ('P005', '营养罐头', '食品', 25.00, 5, '在售');

INSERT INTO Inventory (inventory_id, product_id, quantity, update_time)
VALUES ('I005', 'P005', 40, GETDATE());

INSERT INTO InventoryLog (log_id, product_id, change_type, change_qty, change_time, remark)
VALUES ('L005', 'P005', '入库', 40, GETDATE(), '新增商品入库');
GO

-- 2. 新增合法订单与明细（小计 = 数量 × 单价）
INSERT INTO Orders (order_id, member_id, employee_id, order_type, order_time, total_amount, pay_method, order_status)
VALUES ('O2025010103', 'M002', 'E002', '商品', '2025-01-02 15:00:00', 50.00, '支付宝', '已完成');

INSERT INTO OrderDetail (detail_id, order_id, product_id, quantity, unit_price, subtotal)
VALUES ('D003', 'O2025010103', 'P005', 2, 25.00, 50.00);
GO

-- ============================================================
-- 三、验证：非法数据（应失败并被拒绝）
-- ============================================================

-- 1. 商品名称 + 类别重复 → 违反 UQ_Product_NameCategory
INSERT INTO Product (product_id, product_name, category, price, stock_warn, status)
VALUES ('P006', '营养罐头', '食品', 20.00, 5, '在售');
GO

-- 2. 小计与数量 × 单价不符 → 违反 CK_OrderDetail_Subtotal
INSERT INTO OrderDetail (detail_id, order_id, product_id, quantity, unit_price, subtotal)
VALUES ('D004', 'O2025010103', 'P001', 2, 128.00, 100.00);
GO

-- 3. 入库数量为负 → 违反 CK_InventoryLog_Sign
INSERT INTO InventoryLog (log_id, product_id, change_type, change_qty, change_time, remark)
VALUES ('L006', 'P005', '入库', -5, GETDATE(), '非法入库');
GO

-- 4. 引用不存在的商品 → 违反外码约束（product_id 引用 Product）
INSERT INTO OrderDetail (detail_id, order_id, product_id, quantity, unit_price, subtotal)
VALUES ('D005', 'O2025010103', 'P999', 1, 10.00, 10.00);
GO

-- 5. 非法支付方式 → 违反 CK_Orders_pay_method（第3周已定义）
INSERT INTO Orders (order_id, member_id, employee_id, order_type, total_amount, pay_method)
VALUES ('O2025010104', 'M001', 'E002', '商品', 10.00, '刷卡');
GO

-- ============================================================
-- 四、清理验证数据（恢复原始样例状态，保证 v0.1 可复现）
-- ============================================================

DELETE FROM OrderDetail  WHERE detail_id    = 'D003';
DELETE FROM Orders       WHERE order_id     = 'O2025010103';
DELETE FROM InventoryLog WHERE log_id       = 'L005';
DELETE FROM Inventory    WHERE inventory_id = 'I005';
DELETE FROM Product      WHERE product_id   = 'P005';
GO
