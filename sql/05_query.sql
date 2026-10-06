-- 05_query.sql
-- PetCare 宠物店管理系统
-- 功能：多表连接查询、聚合统计、子查询（第4周）

USE PetCareDB;
GO

-- ============================================================
-- 一、多表连接查询（INNER JOIN / LEFT JOIN）
-- ============================================================

-- 1. 订单详情：订单 × 明细 × 商品 × 员工 × 会员
--    业务问题：每张订单买了哪些商品、由谁经手、卖给哪位顾客
SELECT o.order_id, o.order_time, o.pay_method,
       ISNULL(m.member_name, '散客') AS member_name,
       e.employee_name,
       p.product_name, d.quantity, d.unit_price, d.subtotal
FROM Orders o
JOIN OrderDetail d ON o.order_id = d.order_id
JOIN Product p     ON d.product_id = p.product_id
JOIN Employee e    ON o.employee_id = e.employee_id
LEFT JOIN Member m ON o.member_id = m.member_id;
GO

-- 2. INNER JOIN 与 LEFT JOIN 的区别
--    业务问题：散客订单 member_id 为 NULL，INNER JOIN 会丢失散客订单
-- 2.1 INNER JOIN：只保留能匹配到会员的订单（散客订单丢失）
SELECT o.order_id, m.member_name
FROM Orders o
JOIN Member m ON o.member_id = m.member_id;
GO

-- 2.2 LEFT JOIN：保留所有订单，散客订单的会员名为 NULL
SELECT o.order_id, m.member_name
FROM Orders o
LEFT JOIN Member m ON o.member_id = m.member_id;
GO

-- 3. 服务预约详情：预约 × 服务 × 会员 × 员工
SELECT a.appointment_id, s.service_name, s.price,
       ISNULL(m.member_name, '散客') AS member_name,
       e.employee_name, a.appoint_time, a.status
FROM ServiceAppointment a
JOIN PetService s    ON a.service_id = s.service_id
LEFT JOIN Member m   ON a.member_id = m.member_id
LEFT JOIN Employee e ON a.employee_id = e.employee_id;
GO

-- ============================================================
-- 二、聚合统计（GROUP BY / HAVING）
-- ============================================================

-- 4. 会员消费统计：订单数、消费总额（LEFT JOIN 保证没消费的会员也在结果里）
SELECT m.member_id, m.member_name,
       COUNT(o.order_id) AS order_count,
       ISNULL(SUM(o.total_amount), 0) AS total_spent
FROM Member m
LEFT JOIN Orders o ON m.member_id = o.member_id
GROUP BY m.member_id, m.member_name;
GO

-- 5. 商品销量排行：按销量降序
SELECT p.product_id, p.product_name, p.category,
       ISNULL(SUM(d.quantity), 0) AS sold_qty,
       ISNULL(SUM(d.subtotal), 0) AS sales_amount
FROM Product p
LEFT JOIN OrderDetail d ON p.product_id = d.product_id
GROUP BY p.product_id, p.product_name, p.category
ORDER BY sold_qty DESC;
GO

-- 6. HAVING：消费总额超过 50 元的会员
SELECT m.member_id, m.member_name, SUM(o.total_amount) AS total_spent
FROM Member m
JOIN Orders o ON m.member_id = o.member_id
GROUP BY m.member_id, m.member_name
HAVING SUM(o.total_amount) > 50;
GO

-- ============================================================
-- 三、子查询
-- ============================================================

-- 7. 库存不足预警：当前库存低于安全库存的商品
--    （当前样例数据库存均充足，故结果为空，属正常业务结果）
SELECT p.product_id, p.product_name, i.quantity, p.stock_warn
FROM Product p
JOIN Inventory i ON p.product_id = i.product_id
WHERE i.quantity < p.stock_warn;
GO

-- 8. 子查询（IN）：还有未完成预约的会员
SELECT m.member_id, m.member_name, m.phone
FROM Member m
WHERE m.member_id IN (
    SELECT member_id
    FROM ServiceAppointment
    WHERE status = '已预约' AND member_id IS NOT NULL
);
GO

-- 9. 子查询（标量）：销量最高的商品
SELECT product_name, price
FROM Product
WHERE product_id = (
    SELECT TOP 1 product_id
    FROM OrderDetail
    GROUP BY product_id
    ORDER BY SUM(quantity) DESC, SUM(subtotal) DESC
);
GO

-- 10. 相关子查询（NOT EXISTS）：尚未产生任何销售的滞销商品
SELECT p.product_id, p.product_name
FROM Product p
WHERE NOT EXISTS (
    SELECT 1 FROM OrderDetail d WHERE d.product_id = p.product_id
);
GO
