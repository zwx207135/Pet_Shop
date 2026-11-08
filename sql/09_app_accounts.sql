-- ============================================================
-- 09_app_accounts.sql
-- PetCareDB v1.0 应用受限账户与权限
--
-- 设计：
--   petcare_auth    ：只读 v_employee_login，专用于登录校验；
--   petcare_clerk   ：店员，映射 role_clerk；
--   petcare_manager ：店长，映射 role_manager。
--
-- 原有 clerk_user / manager_user 是 WITHOUT LOGIN 用户，只用于
-- EXECUTE AS 回归测试和课堂演示，不能让 pyodbc 登录，故保留。
--
-- 运行前提：已执行 sql/migration.sql；以 sysadmin 身份执行。
-- 开发环境密码仅用于课程演示，生产环境必须改为环境变量注入。
-- ============================================================

USE master;
GO

IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = 'petcare_auth')
    CREATE LOGIN petcare_auth
        WITH PASSWORD = 'PetCare#Auth2026!', CHECK_POLICY = OFF;

IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = 'petcare_clerk')
    CREATE LOGIN petcare_clerk
        WITH PASSWORD = 'PetCare#Clerk2026!', CHECK_POLICY = OFF;

IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = 'petcare_manager')
    CREATE LOGIN petcare_manager
        WITH PASSWORD = 'PetCare#Manager2026!', CHECK_POLICY = OFF;
GO

USE PetCareDB;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.database_principals
    WHERE name = 'petcare_auth' AND type = 'S'
)
    CREATE USER petcare_auth FOR LOGIN petcare_auth;

IF NOT EXISTS (
    SELECT 1 FROM sys.database_principals
    WHERE name = 'petcare_clerk' AND type = 'S'
)
    CREATE USER petcare_clerk FOR LOGIN petcare_clerk;

IF NOT EXISTS (
    SELECT 1 FROM sys.database_principals
    WHERE name = 'petcare_manager' AND type = 'S'
)
    CREATE USER petcare_manager FOR LOGIN petcare_manager;
GO

-- 角色成员关系（可重复执行）
IF NOT EXISTS (
    SELECT 1
    FROM sys.database_role_members rm
    JOIN sys.database_principals r ON rm.role_principal_id = r.principal_id
    JOIN sys.database_principals m ON rm.member_principal_id = m.principal_id
    WHERE r.name = 'role_clerk' AND m.name = 'petcare_clerk'
)
    ALTER ROLE role_clerk ADD MEMBER petcare_clerk;

IF NOT EXISTS (
    SELECT 1
    FROM sys.database_role_members rm
    JOIN sys.database_principals r ON rm.role_principal_id = r.principal_id
    JOIN sys.database_principals m ON rm.member_principal_id = m.principal_id
    WHERE r.name = 'role_manager' AND m.name = 'petcare_manager'
)
    ALTER ROLE role_manager ADD MEMBER petcare_manager;
GO

-- ============================================================
-- 修正 v0.1 权限缺口
-- ============================================================

-- 店员下单必须扣库存，v0.1 只给了 SELECT
GRANT UPDATE ON dbo.Inventory TO role_clerk;

-- 店员看不到 Employee 基表，订单页通过 v_order_header 获取员工姓名；
-- 视图必须显式授权，所有权链才会生效。
GRANT SELECT ON dbo.v_order_header       TO role_clerk, role_manager;
GRANT SELECT ON dbo.v_order_detail       TO role_clerk, role_manager;
GRANT SELECT ON dbo.v_inventory_status   TO role_clerk, role_manager;
GRANT SELECT ON dbo.v_product_sales      TO role_clerk, role_manager;
GRANT SELECT ON dbo.v_member_consumption TO role_clerk, role_manager;
GRANT SELECT ON dbo.v_service_appointment TO role_clerk, role_manager;

-- 登录账号只读取凭据视图，不授予任何业务表权限
GRANT SELECT ON dbo.v_employee_login TO petcare_auth;

-- ============================================================
-- 主键 SEQUENCE 权限
-- NEXT VALUE FOR 需要序列对象的 UPDATE 权限，否则受限账户下单
-- 会在生成主键时报 229。按角色实际用到的序列最小授予。
-- ============================================================
GRANT UPDATE ON OBJECT::dbo.SEQ_Member          TO role_clerk;
GRANT UPDATE ON OBJECT::dbo.SEQ_Order           TO role_clerk;
GRANT UPDATE ON OBJECT::dbo.SEQ_OrderDetail     TO role_clerk;
GRANT UPDATE ON OBJECT::dbo.SEQ_InventoryLog    TO role_clerk;

GRANT UPDATE ON OBJECT::dbo.SEQ_Product             TO role_manager;
GRANT UPDATE ON OBJECT::dbo.SEQ_Inventory           TO role_manager;
GRANT UPDATE ON OBJECT::dbo.SEQ_InventoryLog        TO role_manager;
GRANT UPDATE ON OBJECT::dbo.SEQ_Member              TO role_manager;
GRANT UPDATE ON OBJECT::dbo.SEQ_Employee            TO role_manager;
GRANT UPDATE ON OBJECT::dbo.SEQ_Order               TO role_manager;
GRANT UPDATE ON OBJECT::dbo.SEQ_OrderDetail         TO role_manager;
GRANT UPDATE ON OBJECT::dbo.SEQ_PetService          TO role_manager;
GRANT UPDATE ON OBJECT::dbo.SEQ_ServiceAppointment  TO role_manager;
GO

PRINT 'Application accounts and role grants are ready.';
GO
