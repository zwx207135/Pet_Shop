-- 02_create_tables.sql
-- PetCare 宠物店管理系统
-- 功能：创建所有数据表

USE PetCareDB;
GO

-- ==============================
-- 1. Product 商品表
-- ==============================
CREATE TABLE Product (
    product_id CHAR(8) PRIMARY KEY,
    product_name VARCHAR(50) NOT NULL,
    category VARCHAR(20),
    price DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (price >= 0),
    stock_warn INT NOT NULL DEFAULT 10 CHECK (stock_warn >= 0),
    status VARCHAR(10) NOT NULL DEFAULT '在售' CHECK (status IN ('在售','停售'))
);
GO

-- ==============================
-- 2. Inventory 库存表
-- ==============================
CREATE TABLE Inventory (
    inventory_id CHAR(8) PRIMARY KEY,
    product_id CHAR(8) NOT NULL UNIQUE,
    quantity INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    update_time DATETIME NOT NULL DEFAULT GETDATE(),
    FOREIGN KEY (product_id) REFERENCES Product(product_id)
);
GO

-- ==============================
-- 3. InventoryLog 库存变化记录表
-- ==============================
CREATE TABLE InventoryLog (
    log_id CHAR(10) PRIMARY KEY,
    product_id CHAR(8) NOT NULL,
    change_type VARCHAR(10) NOT NULL CHECK (change_type IN ('入库','销售')),
    change_qty INT NOT NULL CHECK (change_qty <> 0),
    change_time DATETIME NOT NULL DEFAULT GETDATE(),
    remark VARCHAR(100),
    FOREIGN KEY (product_id) REFERENCES Product(product_id)
);
GO

-- ==============================
-- 4. Member 会员表
-- ==============================
CREATE TABLE Member (
    member_id CHAR(8) PRIMARY KEY,
    member_name VARCHAR(30) NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE,
    points INT NOT NULL DEFAULT 0 CHECK (points >= 0),
    join_date DATE NOT NULL DEFAULT GETDATE()
);
GO

-- ==============================
-- 5. Employee 员工表
-- ==============================
CREATE TABLE Employee (
    employee_id CHAR(8) PRIMARY KEY,
    employee_name VARCHAR(30) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('店长','店员')),
    phone VARCHAR(20) UNIQUE,
    hire_date DATE NOT NULL DEFAULT GETDATE()
);
GO

-- ==============================
-- 6. Orders 订单表
-- ==============================
CREATE TABLE Orders (
    order_id CHAR(12) PRIMARY KEY,
    member_id CHAR(8),
    employee_id CHAR(8) NOT NULL,
    order_type VARCHAR(10) NOT NULL DEFAULT '商品' CHECK (order_type IN ('商品','服务')),
    order_time DATETIME NOT NULL DEFAULT GETDATE(),
    total_amount DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    pay_method VARCHAR(10) NOT NULL DEFAULT '现金' CHECK (pay_method IN ('现金','微信','支付宝')),
    order_status VARCHAR(10) NOT NULL DEFAULT '已完成' CHECK (order_status IN ('已完成','未完成')),
    FOREIGN KEY (member_id) REFERENCES Member(member_id),
    FOREIGN KEY (employee_id) REFERENCES Employee(employee_id)
);
GO

-- ==============================
-- 7. OrderDetail 订单明细表
-- ==============================
CREATE TABLE OrderDetail (
    detail_id CHAR(10) PRIMARY KEY,
    order_id CHAR(12) NOT NULL,
    product_id CHAR(8) NOT NULL,
    quantity INT NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price DECIMAL(10,2) NOT NULL CHECK (unit_price >= 0),
    subtotal DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    FOREIGN KEY (order_id) REFERENCES Orders(order_id),
    FOREIGN KEY (product_id) REFERENCES Product(product_id)
);
GO

-- ==============================
-- 8. PetService 宠物服务表
-- ==============================
CREATE TABLE PetService (
    service_id CHAR(8) PRIMARY KEY,
    service_name VARCHAR(50) NOT NULL,
    price DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (price >= 0),
    duration_min INT,
    status VARCHAR(10) NOT NULL DEFAULT '可用' CHECK (status IN ('可用','停用'))
);
GO

-- ==============================
-- 9. ServiceAppointment 服务预约表
-- ==============================
CREATE TABLE ServiceAppointment (
    appointment_id CHAR(10) PRIMARY KEY,
    member_id CHAR(8),
    service_id CHAR(8) NOT NULL,
    employee_id CHAR(8),
    appoint_time DATETIME NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT '已预约' CHECK (status IN ('已预约','已完成','已取消')),
    remark VARCHAR(100),
    FOREIGN KEY (member_id) REFERENCES Member(member_id),
    FOREIGN KEY (service_id) REFERENCES PetService(service_id),
    FOREIGN KEY (employee_id) REFERENCES Employee(employee_id)
);
GO