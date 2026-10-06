# 第3周任务：DDL 与数据修改

## 一、本周目标

使用 SQL 脚本从空数据库开始创建 PetCareDB，建立商品、库存、订单、订单明细、会员、员工、宠物服务、服务预约等业务对象，完成基础数据的新增、修改、删除和查询。

## 二、建库

脚本：`sql/01_create_database.sql`

功能：

- 如果 PetCareDB 已存在，先删除，方便复现。
- 创建数据库 PetCareDB。
- 切换到 PetCareDB。

## 三、建表

脚本：`sql/02_create_tables.sql`

共创建 9 张表：

| 表名 | 说明 |
|---|---|
| Product | 商品表 |
| Inventory | 库存表 |
| InventoryLog | 库存变化记录表 |
| Member | 会员表 |
| Employee | 员工表 |
| Orders | 订单表 |
| OrderDetail | 订单明细表 |
| PetService | 宠物服务表 |
| ServiceAppointment | 服务预约表 |

建表顺序遵循：先建被外码引用的表，再建引用它的表。

## 四、插入样例数据

脚本：`sql/03_insert_data.sql`

插入顺序：

1. Product
2. Inventory
3. InventoryLog
4. Member
5. Employee
6. Orders
7. OrderDetail
8. PetService
9. ServiceAppointment

## 五、CRUD 演示

脚本：`sql/04_crud.sql`

包含：

1. 新增
   - 新增商品 P004 猫砂10L
   - 新增库存 I004
   - 新增库存变化记录 L004
2. 查询
   - 查询所有在售商品
   - 查询商品及库存
   - 查询订单及明细
3. 修改
   - 修改 P004 价格
   - 修改 P004 库存
4. 删除
   - 删除前先 SELECT 确认
   - 按引用顺序删除：InventoryLog → Inventory → Product
   - 删除后再 SELECT 确认

## 六、执行结果

截图见 `result/` 目录。

| 截图 | 说明 |
|---|---|
| 01_建库成功.png | PetCareDB 创建成功 |
| 02_建表成功.png | 9 张表创建成功 |
| 03_插入数据.png | 样例数据插入成功 |
| 04_CRUD_插入结果.png | 新增 P004 成功 |
| 05_CRUD_查询结果.png | 多表查询结果 |
| 06_CRUD_修改结果.png | P004 价格与库存修改成功 |
| 07_CRUD_删除结果.png | P004 相关数据删除成功 |

## 七、复现说明

1. 打开 SSMS，连接本地 SQL Server。
2. 新建查询，执行 `sql/01_create_database.sql`。
3. 新建查询，执行 `sql/02_create_tables.sql`。
4. 新建查询，执行 `sql/03_insert_data.sql`。
5. 新建查询，执行 `sql/04_crud.sql`。
6. 从空库复现：先执行 `DROP DATABASE PetCareDB;`，再从第 2 步开始。

## 八、遇到的问题与解决
