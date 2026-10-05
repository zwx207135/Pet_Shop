-- 04_crud.sql
-- PetCare 宠物店管理系统
-- 功能：演示增删改查（CRUD）

USE PetCareDB;
GO

-- ==============================================
-- 一、新增（Insert）
-- ==============================================

-- 1. 新增一个商品
INSERT INTO Product (product_id, product_name, category, price, stock_warn, status)
VALUES ('P004', '猫砂10L', '用品', 39.90, 5, '在售');
GO

-- 2. 为新商品新增库存记录
INSERT INTO Inventory (inventory_id, product_id, quantity, update_time)
VALUES ('I004', 'P004', 30, GETDATE());
GO

-- 3. 新增一条库存变化记录
INSERT INTO InventoryLog (log_id, product_id, change_type, change_qty, change_time, remark)
VALUES ('L004', 'P004', '入库', 30, GETDATE(), '新增商品入库');
GO

-- ==============================================
-- 二、查询（Select）
-- ==============================================

-- 1. 查询所有在售商品
SELECT * FROM Product WHERE status = '在售';
GO

-- 2. 查询商品及其当前库存
SELECT p.product_id, p.product_name, p.price, i.quantity, i.update_time
FROM Product p
JOIN Inventory i ON p.product_id = i.product_id;
GO

-- 3. 查询订单及订单明细
SELECT o.order_id, o.order_time, p.product_name, d.quantity, d.unit_price, d.subtotal
FROM Orders o
JOIN OrderDetail d ON o.order_id = d.order_id
JOIN Product p ON d.product_id = p.product_id;
GO

-- ==============================================
-- 三、修改（Update）
-- ==============================================

-- 1. 修改商品价格
UPDATE Product
SET price = 42.00
WHERE product_id = 'P004';
GO

-- 2. 修改库存数量
UPDATE Inventory
SET quantity = 25, update_time = GETDATE()
WHERE product_id = 'P004';
GO

-- 3. 修改后查询确认
SELECT * FROM Product WHERE product_id = 'P004';
SELECT * FROM Inventory WHERE product_id = 'P004';
GO

-- ==============================================
-- 四、删除（Delete）
-- ==============================================

-- 1. 删除前先查询确认目标行
SELECT * FROM InventoryLog WHERE product_id = 'P004';
SELECT * FROM Inventory WHERE product_id = 'P004';
SELECT * FROM Product WHERE product_id = 'P004';
GO

-- 2. 按引用顺序删除：先删日志，再删库存，最后删商品
DELETE FROM InventoryLog WHERE product_id = 'P004';
DELETE FROM Inventory WHERE product_id = 'P004';
DELETE FROM Product WHERE product_id = 'P004';
GO

-- 3. 删除后查询确认
SELECT * FROM Product WHERE product_id = 'P004';
SELECT * FROM Inventory WHERE product_id = 'P004';
SELECT * FROM InventoryLog WHERE product_id = 'P004';
GO