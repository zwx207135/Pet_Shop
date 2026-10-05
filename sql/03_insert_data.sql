-- 03_insert_data.sql
-- PetCare 宠物店管理系统
-- 功能：插入样例数据

USE PetCareDB;
GO

-- ==============================
-- 1. Product 商品表
-- ==============================
INSERT INTO Product (product_id, product_name, category, price, stock_warn, status) VALUES
('P001', '皇家猫粮2kg', '食品', 128.00, 5, '在售'),
('P002', '狗狗磨牙棒', '玩具', 19.90, 10, '在售'),
('P003', '宠物牵引绳', '用品', 45.00, 5, '在售');
GO

-- ==============================
-- 2. Inventory 库存表
-- ==============================
INSERT INTO Inventory (inventory_id, product_id, quantity, update_time) VALUES
('I001', 'P001', 20, '2025-01-01 10:00:00'),
('I002', 'P002', 50, '2025-01-01 10:00:00'),
('I003', 'P003', 15, '2025-01-01 10:00:00');
GO

-- ==============================
-- 3. InventoryLog 库存变化记录表
-- ==============================
INSERT INTO InventoryLog (log_id, product_id, change_type, change_qty, change_time, remark) VALUES
('L001', 'P001', '入库', 20, '2025-01-01 09:00:00', '初始入库'),
('L002', 'P002', '入库', 50, '2025-01-01 09:00:00', '初始入库'),
('L003', 'P001', '销售', -1, '2025-01-01 10:30:00', '订单O2025010101');
GO

-- ==============================
-- 4. Member 会员表
-- ==============================
INSERT INTO Member (member_id, member_name, phone, points, join_date) VALUES
('M001', '张三', '13800000001', 100, '2025-01-01'),
('M002', '李四', '13800000002', 50, '2025-01-02');
GO

-- ==============================
-- 5. Employee 员工表
-- ==============================
INSERT INTO Employee (employee_id, employee_name, role, phone, hire_date) VALUES
('E001', '王店长', '店长', '13900000001', '2024-01-01'),
('E002', '赵店员', '店员', '13900000002', '2024-02-01');
GO

-- ==============================
-- 6. Orders 订单表
-- ==============================
INSERT INTO Orders (order_id, member_id, employee_id, order_type, order_time, total_amount, pay_method, order_status) VALUES
('O2025010101', 'M001', 'E002', '商品', '2025-01-01 10:30:00', 128.00, '微信', '已完成'),
('O2025010102', NULL, 'E002', '商品', '2025-01-01 11:00:00', 19.90, '现金', '已完成');
GO

-- ==============================
-- 7. OrderDetail 订单明细表
-- ==============================
INSERT INTO OrderDetail (detail_id, order_id, product_id, quantity, unit_price, subtotal) VALUES
('D001', 'O2025010101', 'P001', 1, 128.00, 128.00),
('D002', 'O2025010102', 'P002', 1, 19.90, 19.90);
GO

-- ==============================
-- 8. PetService 宠物服务表
-- ==============================
INSERT INTO PetService (service_id, service_name, price, duration_min, status) VALUES
('SV001', '宠物洗护', 80.00, 60, '可用'),
('SV002', '宠物美容', 150.00, 90, '可用'),
('SV003', '指甲修剪', 30.00, 20, '可用');
GO

-- ==============================
-- 9. ServiceAppointment 服务预约表
-- ==============================
INSERT INTO ServiceAppointment (appointment_id, member_id, service_id, employee_id, appoint_time, status, remark) VALUES
('A001', 'M001', 'SV001', 'E002', '2025-01-03 14:00:00', '已预约', '无'),
('A002', 'M002', 'SV003', 'E002', '2025-01-04 10:00:00', '已完成', '无');
GO