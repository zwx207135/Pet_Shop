-- 08_role.sql
-- PetCare 宠物店管理系统
-- 功能：数据库角色划分、最小权限授予、越权测试（第4周）

USE PetCareDB;
GO

-- ============================================================
-- 一、创建数据库角色（对应第1周角色清单）
--    说明：会员/顾客不直接连接数据库，而是通过应用系统访问，
--          因此不建立数据库角色；店长、店员、系统管理员需要
--          直接操作数据库，分别建立角色。
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'role_manager' AND type = 'R')
    CREATE ROLE role_manager;   -- 店长
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'role_clerk' AND type = 'R')
    CREATE ROLE role_clerk;     -- 店员
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'role_admin' AND type = 'R')
    CREATE ROLE role_admin;     -- 系统管理员
GO

-- ============================================================
-- 二、授予最小权限
-- ============================================================

-- 1. 店员 role_clerk：接待、销售、办会员、登记预约，不授予删除和查看员工
GRANT SELECT, INSERT, UPDATE ON dbo.Member              TO role_clerk;
GRANT SELECT                 ON dbo.Product             TO role_clerk;
GRANT SELECT                 ON dbo.Inventory           TO role_clerk;
GRANT SELECT, INSERT         ON dbo.InventoryLog        TO role_clerk;
GRANT SELECT, INSERT, UPDATE ON dbo.Orders              TO role_clerk;
GRANT SELECT, INSERT, UPDATE ON dbo.OrderDetail         TO role_clerk;
GRANT SELECT                 ON dbo.PetService          TO role_clerk;
GRANT SELECT, INSERT, UPDATE ON dbo.ServiceAppointment  TO role_clerk;
GO

-- 2. 店长 role_manager：在店员基础上，增加商品、库存、服务、员工、订单的管理权限
GRANT SELECT, INSERT, UPDATE ON dbo.Member               TO role_manager;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.Product            TO role_manager;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.Inventory          TO role_manager;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.InventoryLog       TO role_manager;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.Employee           TO role_manager;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.Orders             TO role_manager;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.OrderDetail        TO role_manager;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.PetService         TO role_manager;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.ServiceAppointment TO role_manager;
GO

-- 3. 系统管理员 role_admin：管理账号、角色与权限，不直接操作业务数据
ALTER ROLE db_accessadmin  ADD MEMBER role_admin;   -- 可管理数据库用户
ALTER ROLE db_securityadmin ADD MEMBER role_admin;  -- 可管理角色与成员
GO

-- ============================================================
-- 三、创建数据库用户并加入角色
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'clerk_user' AND type = 'S')
    CREATE USER clerk_user WITHOUT LOGIN;
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'manager_user' AND type = 'S')
    CREATE USER manager_user WITHOUT LOGIN;
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'admin_user' AND type = 'S')
    CREATE USER admin_user WITHOUT LOGIN;
GO

ALTER ROLE role_clerk   ADD MEMBER clerk_user;
ALTER ROLE role_manager ADD MEMBER manager_user;
ALTER ROLE role_admin   ADD MEMBER admin_user;
GO

-- ============================================================
-- 四、权限验证
-- ============================================================

-- 1. 店员正常操作：查询商品与库存（应成功）
EXECUTE AS USER = 'clerk_user';
SELECT p.product_id, p.product_name, i.quantity
FROM Product p
JOIN Inventory i ON p.product_id = i.product_id;
REVERT;
GO

-- 2. 店员正常操作：办理订单（应成功，事务回滚仅作演示）
EXECUTE AS USER = 'clerk_user';
BEGIN TRAN;
INSERT INTO Orders (order_id, member_id, employee_id, order_type, total_amount)
VALUES ('OTEST0001', 'M001', 'E002', '商品', 128.00);
ROLLBACK TRAN;
REVERT;
GO

-- 3. 越权：店员尝试查看员工表（应失败，提示对象名无效/权限不足）
EXECUTE AS USER = 'clerk_user';
SELECT * FROM Employee;
REVERT;
GO

-- 4. 越权：店员尝试删除商品（应失败）
EXECUTE AS USER = 'clerk_user';
DELETE FROM Product WHERE product_id = 'P001';
REVERT;
GO

-- 5. 越权：店员尝试删除订单（应失败）
EXECUTE AS USER = 'clerk_user';
DELETE FROM Orders WHERE order_id = 'O2025010101';
REVERT;
GO

-- 6. 店长正常操作：查看员工、修改商品价格（应成功，事务回滚）
EXECUTE AS USER = 'manager_user';
SELECT employee_id, employee_name, role FROM Employee;
BEGIN TRAN;
UPDATE Product SET price = 130.00 WHERE product_id = 'P001';
ROLLBACK TRAN;
REVERT;
GO

-- 7. 查看角色与成员关系（验证角色划分）
SELECT CAST(r.name AS VARCHAR(20)) AS role_name, CAST(m.name AS VARCHAR(20)) AS member_name
FROM sys.database_role_members rm
JOIN sys.database_principals r ON rm.role_principal_id = r.principal_id
JOIN sys.database_principals m ON rm.member_principal_id = m.principal_id
WHERE r.name IN ('role_clerk', 'role_manager', 'role_admin')
ORDER BY r.name, m.name;
GO
