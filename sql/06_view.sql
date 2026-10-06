-- 06_view.sql
-- PetCare 宠物店管理系统
-- 功能：创建统计视图并验证（第4周）

USE PetCareDB;
GO

-- ============================================================
-- 一、创建统计视图
-- ============================================================

-- 1. 订单详情视图：封装订单、明细、商品、员工、会员的复杂连接，供重复查询使用
CREATE VIEW dbo.v_order_detail AS
SELECT o.order_id, o.order_time, o.pay_method, o.order_status,
       ISNULL(m.member_name, '散客') AS member_name,
       e.employee_name,
       p.product_name, d.quantity, d.unit_price, d.subtotal
FROM Orders o
JOIN OrderDetail d ON o.order_id = d.order_id
JOIN Product p     ON d.product_id = p.product_id
JOIN Employee e    ON o.employee_id = e.employee_id
LEFT JOIN Member m ON o.member_id = m.member_id;
GO

-- 2. 商品销售统计视图：统计每种商品的销量与销售额
CREATE VIEW dbo.v_product_sales AS
SELECT p.product_id, p.product_name, p.category, p.price,
       ISNULL(SUM(d.quantity), 0) AS sold_qty,
       ISNULL(SUM(d.subtotal), 0) AS sales_amount
FROM Product p
LEFT JOIN OrderDetail d ON p.product_id = d.product_id
GROUP BY p.product_id, p.product_name, p.category, p.price;
GO

-- 3. 库存状态视图：展示库存数量并判断库存状态
CREATE VIEW dbo.v_inventory_status AS
SELECT p.product_id, p.product_name, i.quantity, p.stock_warn,
       CASE
           WHEN i.quantity = 0 THEN '缺货'
           WHEN i.quantity < p.stock_warn THEN '库存不足'
           ELSE '正常'
       END AS stock_status
FROM Product p
JOIN Inventory i ON p.product_id = i.product_id;
GO

-- 4. 会员消费统计视图：统计会员订单数与消费总额
CREATE VIEW dbo.v_member_consumption AS
SELECT m.member_id, m.member_name, m.points,
       COUNT(o.order_id) AS order_count,
       ISNULL(SUM(o.total_amount), 0) AS total_spent
FROM Member m
LEFT JOIN Orders o ON m.member_id = o.member_id
GROUP BY m.member_id, m.member_name, m.points;
GO

-- 5. 服务预约视图：预约、服务、会员、员工的连接结果
CREATE VIEW dbo.v_service_appointment AS
SELECT a.appointment_id, s.service_name, s.price,
       ISNULL(m.member_name, '散客') AS member_name,
       e.employee_name, a.appoint_time, a.status
FROM ServiceAppointment a
JOIN PetService s    ON a.service_id = s.service_id
LEFT JOIN Member m   ON a.member_id = m.member_id
LEFT JOIN Employee e ON a.employee_id = e.employee_id;
GO

-- ============================================================
-- 二、验证视图查询结果
-- ============================================================

-- 1. 查看订单详情视图
SELECT * FROM dbo.v_order_detail;
GO

-- 2. 查看商品销售统计视图
SELECT * FROM dbo.v_product_sales;
GO

-- 3. 查看库存状态视图
SELECT * FROM dbo.v_inventory_status;
GO

-- 4. 查看会员消费统计视图
SELECT * FROM dbo.v_member_consumption;
GO

-- 5. 查看服务预约视图
SELECT * FROM dbo.v_service_appointment;
GO

-- 6. 基于视图的进一步统计：销售额最高的商品
SELECT TOP 1 product_name, sales_amount
FROM dbo.v_product_sales
ORDER BY sales_amount DESC;
GO
