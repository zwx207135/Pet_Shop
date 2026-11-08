# PetCare 宠物店管理系统

数据库实验课程项目，贯穿第1—17周。当前仓库完成第1—9周数据侧内容：v1.0 数据库、迁移与回归、DAO 数据访问层、受限账号、集成测试。

## 一、项目范围

PetCare 宠物店管理系统，包含以下核心业务：

- 商品管理
- 库存管理
- 会员管理
- 商品销售与订单管理
- 订单明细管理
- 会员积分管理
- 宠物服务管理
- 服务预约与消费管理
- 员工及经营角色管理

## 二、业务角色

| 角色       | 主要职责                                                       |
| ---------- | -------------------------------------------------------------- |
| 店长       | 门店整体经营、商品与库存管理、员工管理、经营数据查看、补货管理 |
| 店员       | 接待顾客、商品销售、订单处理、会员办理、宠物服务登记           |
| 会员/顾客  | 购买商品、预约宠物服务、参与会员积分活动                       |
| 系统管理员 | 系统账号、角色和权限维护                                       |

## 三、业务流程

1. 顾客到店
2. 判断是否会员：是则查询会员信息，否则可注册会员
3. 选择商品或宠物服务
4. 购买商品：查询库存 → 创建订单 → 添加订单明细 → 计算金额 → 支付 → 扣减库存
5. 预约服务：选择服务项目 → 确认预约时间 → 创建服务预约 → 完成服务 → 支付
6. 记录消费信息
7. 计算并更新会员积分
8. 完成交易

## 四、核心业务对象

| 业务对象 | 说明                               |
| -------- | ---------------------------------- |
| 商品     | 宠物食品、宠物用品等可销售商品     |
| 库存     | 记录商品当前库存及库存变化         |
| 订单     | 记录一次完整的商品或服务消费       |
| 订单明细 | 记录订单中具体购买的商品           |
| 会员     | 记录会员基本信息及会员积分         |
| 员工     | 记录店长、店员等工作人员信息       |
| 宠物服务 | 记录宠物店提供的服务项目           |
| 服务预约 | 记录会员或顾客的服务预约及消费信息 |

## 五、目录结构

```text
Pet_Shop-main/
├─ dao/                    Python 数据访问层
│  ├─ config.py            读取 .env，构造三种角色的连接串
│  ├─ database.py          连接与事务入口
│  ├─ errors.py            DAOError、错误码、SQL Server 错误翻译
│  ├─ ids.py               SEQUENCE 主键生成
│  ├─ models.py            Page、OrderItemInput
│  ├─ product_dao.py       商品
│  ├─ inventory_dao.py     库存与库存流水
│  ├─ order_dao.py         订单与订单明细
│  ├─ member_dao.py        会员
│  ├─ employee_dao.py      员工与登录凭据
│  └─ report_dao.py        统计视图查询
├─ sql/                    建库、迁移、权限、回归脚本
├─ tests/                  DAO 集成测试
├─ scripts/                测试库克隆、SQL 执行、第5周验证、结果采集
├─ app/                    Flask Web 应用（成员B）
│  ├─ __init__.py          应用工厂、模板过滤器
│  ├─ config.py            Flask 配置（会话密钥等）
│  ├─ extensions.py        Database 单例（连接管理）
│  ├─ security.py          登录态与角色权限装饰器
│  ├─ services/            业务层：登录/商品/库存/订单/会员/员工/报表
│  ├─ routes/              页面层：路由蓝图
│  ├─ errors/              统一异常处理与后端日志
│  ├─ templates/           Jinja2 模板
│  └─ static/              CSS 等静态资源
├─ docs/                   第1—6周文档、DAO 契约、ER 图
├─ result/                 SQL 执行结果与测试证据
├─ run.py                  Web 应用启动入口
├─ .env.example            环境变量模板
├─ pytest.ini              pytest 配置
└─ README.md
```

## 六、环境与依赖

- SQL Server 2022/2025 Express（数据侧在 2025 Express 17.0、应用侧在 2022 Express 16.0 上验证）；
- ODBC Driver 17 或 18 for SQL Server（数据侧 Driver 18、应用侧 Driver 17，`scripts/create_test_db.py` 自动探测回退）；
- Python 3.11+（数据侧在 Python 3.14、应用侧在 Python 3.13 上验证）；
- Python 包：`pyodbc`、`pytest`、`matplotlib`（仅 ER 图导出）、`werkzeug`（B 的登录密码校验）、`flask`（B 的 Web 框架）。

安装示例：

```bash
py -m pip install -r requirements.txt
# 或逐个安装：pyodbc pytest matplotlib werkzeug flask
```

Windows 上如 `python` 命令不可用，统一使用 `py` 启动器。

## 七、SQL 脚本执行顺序

按以下顺序执行 `sql/` 目录下的脚本：

1. `sql/01_create_database.sql` —— 创建数据库
2. `sql/02_create_tables.sql` —— 创建数据表
3. `sql/03_insert_data.sql` —— 插入样例数据
4. `sql/04_crud.sql` —— 增删改查演示
5. `sql/05_query.sql` —— 多表查询
6. `sql/06_view.sql` —— 统计视图
7. `sql/07_constraint.sql` —— 完整性约束
8. `sql/08_role.sql` —— v0.1 角色与 `WITHOUT LOGIN` 演示用户
9. `sql/migration.sql` —— v0.1 → v1.0：登录字段、计算列、视图、序列、索引
10. `sql/09_app_accounts.sql` —— 应用登录账号、角色成员、表和序列授权
11. `sql/regression.sql` —— 迁移结构、数据、视图、权限、事务回滚回归

注意：

- `sqlcmd` 执行含计算列的表时加 `-I`（`SET QUOTED_IDENTIFIER ON`）；
- 新增 `.sql` 文件使用 UTF-8 BOM，避免中文乱码；
- `migration.sql`、`09_app_accounts.sql`、`regression.sql` 以 sysadmin/dbo 执行；
- 业务连接使用受限账号，不用 sa。

示例：

```bash
sqlcmd -S localhost -E -C -b -I -f 65001 -i sql/migration.sql
sqlcmd -S localhost -E -C -b -I -f 65001 -i sql/09_app_accounts.sql
sqlcmd -S localhost -E -C -b -I -f 65001 -i sql/regression.sql -o result/week9_regression.txt
```

## 八、应用配置

复制模板并填写 `09_app_accounts.sql` 中创建的密码：

```bash
copy .env.example .env
```

`.env` 键：

```text
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_SERVER=localhost
DB_NAME=PetCareDB
DB_AUTH_USER=petcare_auth
DB_AUTH_PASSWORD=...
DB_CLERK_USER=petcare_clerk
DB_CLERK_PASSWORD=...
DB_MANAGER_USER=petcare_manager
DB_MANAGER_PASSWORD=...
DB_ENCRYPT=yes
DB_TRUST_SERVER_CERTIFICATE=yes
DB_TIMEOUT=5
```

`.env` 已加入 `.gitignore`，不得提交真实密码。`DbConfig.from_env()` 会读取这些键，`connection_string(role)` 支持 `"auth"`、`"clerk"`、`"manager"` 三种角色。

## 九、DAO 使用方式

事务边界由 B 的业务层负责；DAO 只使用传入的 `conn`，不 commit、不 rollback、不关闭连接。

```python
from decimal import Decimal

from dao import Database, DbConfig, InventoryDAO, ProductDAO

config = DbConfig.from_env()
db = Database(config)

# 只读
with db.read("clerk") as conn:
    page = ProductDAO().list(conn, keyword="猫粮", page=1, page_size=20)
    for row in page.items:
        print(row["product_id"], row["product_name"], row["price"])

# 写操作：事务由调用方控制
with db.transaction("manager") as conn:
    product = ProductDAO().create(
        conn,
        product_name="测试罐头",
        category="食品",
        price=Decimal("25.00"),
        stock_warn=5,
    )
    InventoryDAO().create(
        conn,
        product_id=product["product_id"],
        quantity=20,
        remark="新商品入库",
    )
```

注意事项：

- `ProductDAO.create` 只插 `Product`；库存行需在同一事务中调用 `InventoryDAO.create`；
- `OrderDAO.create_with_details` 必须在 `db.transaction(...)` 内调用；
- 插入 `OrderDetail` 时不要写 `subtotal`，它是 `PERSISTED` 计算列；
- 受限账号使用 `NEXT VALUE FOR` 需要序列的 `UPDATE` 权限，已由 `09_app_accounts.sql` 授予；
- 不要使用 `with conn.cursor() as cur:`：pyodbc 5.4 在退出时提交事务，会破坏回滚语义；DAO 统一使用 `cursor_scope(conn)`。

## 十、测试

测试使用 `PetCareDB_test`，它是 `PetCareDB` 的克隆，避免污染样例库。

```bash
# 1. 从当前 PetCareDB 克隆测试库
py scripts/create_test_db.py

# 2. 运行全部集成测试
py -m pytest

# 3. 只运行某类测试
py -m pytest tests/test_order_dao.py -v
```

预期结果：数据侧 63 项测试全部通过。测试覆盖：

- 三种角色的连接与 ping、嵌套事务拒绝、异常回滚、成功提交；
- 商品、库存、会员、员工、订单、报表 DAO；
- 权限边界：店员不能建商品、不能读 Employee 基表、auth 只能读登录视图；
- 下单事务：重复商品合并、库存不足整单回滚、停售商品拒绝、并发抢最后一件；
- SQL 注入字符串按普通字面量处理。

测试输出证据：`result/week9_pytest.txt`。

应用侧另有 41 项 DB 无关测试（mock DAO）：`python -m pytest tests/test_app_*.py -q`，覆盖登录鉴权、角色权限、参数校验、错误码→HTTP 映射、统一 JSON 结构与后端日志，证据 `result/week9_app_pytest.txt`。

## 十一、第5—9周文档

| 文档 | 内容 |
| --- | --- |
| `docs/w5_ER模型与规则清单.md` | ER 图、实体/联系、业务规则、v0.1 问题清单、多商品/散客/库存设计验证 |
| `docs/er/petcare_er.svg` / `.png` | ER 图导出 |
| `docs/er/petcare_er.mmd` / `render_er.py` | ER 图可编辑源与导出脚本 |
| `docs/w6_规范化与迁移说明.md` | 函数依赖、3NF/BCNF、迁移步骤、前后回归 |
| `docs/第7-9周_DAO接口约定.md` | v1.0 DAO 契约、错误码、权限、验收用例 |
| `docs/第二阶段报告_数据侧.md` | 第5—9周 A 侧工作总结与交接说明 |
| `docs/第二阶段报告_应用侧.md` | 第7—9周 B 侧工作总结（Flask 应用、异常、角色界面） |

## 十二、设计说明摘要（ER 图 · 依赖分析 · 更新异常 · 范式 · 分解）

本节按第二阶段阶段作业要求，把 ER 与规范化结论直接汇总于此；完整推导见 `docs/w5_ER模型与规则清单.md` 与 `docs/w6_规范化与迁移说明.md`。

### 12.1 ER 模型

- 9 个实体：商品、库存、库存流水、会员、员工、订单、订单明细、服务项目、服务预约；9 条联系（经办、下单、包含、被购买、对应、产生、预约、负责、被预约）。
- 采用 crow's foot 表示法，标注主码、外码、候选码（UNIQUE）、基数与参与约束；图见 `docs/er/petcare_er.svg`（可编辑源 `petcare_er.mmd`，导出脚本 `render_er.py`）。
- 关键基数：`Employee 1—0..N Orders`；`Member 0..1—0..N Orders`（散客 `member_id` 可空）；`Orders 1—1..N OrderDetail`（“至少一条明细”由 DAO 保证）；`Product 1—0..1 Inventory`。

### 12.2 函数依赖（关键）

- 各关系以 `CHAR` 代理码为主码，自然候选码用 `UNIQUE` 保留（如 `Product(product_name, category)`、`Member.phone`、`Employee.login_name`）。
- 唯一的结构性函数依赖问题在 `OrderDetail`：v0.1 的 `subtotal` 是普通列，存在 `{quantity, unit_price} → subtotal`，决定因素不是超码、`subtotal` 不是主属性。

### 12.3 更新异常

- **小计更新异常（主要）**：v0.1 改 `quantity`/`unit_price` 不同时改 `subtotal` 会被 `CK_OrderDetail_Subtotal` 拒绝；若约束被绕过，则订单金额、商品销售额、会员消费全部失真。
- **订单总额漂移**：`Orders.total_amount` 与明细合计语义相同，是跨行聚合冗余（非表内 FD 违反），靠下单事务写入 + `regression.sql` 校验一致。
- **类别/角色文本重复**：`Product.category`、`Employee.role` 重复属字典缺失，不是 3NF 违反；v1.0 保留，列入 v1.1。

### 12.4 范式判断

| 关系 | 3NF | BCNF | 说明 |
|---|---|---|---|
| Product / Inventory / InventoryLog / Member / Employee / Orders / PetService / ServiceAppointment | 是 | 是 | 单属性代理码 + 唯一候选码 |
| OrderDetail（v0.1） | 否 | 否 | `{quantity, unit_price} → subtotal`，`subtotal` 非主属性 |
| OrderDetail（v1.0） | 是 | 是 | `subtotal` 改为 PERSISTED 计算列后，非平凡 FD 的决定因素均为超码 |

### 12.5 分解方案

- 本次**不做关系分解**：只把 `OrderDetail.subtotal` 改为 `PERSISTED` 计算列，消除唯一 3NF/BCNF 违反；因未拆分关系，无损连接与依赖保持自然成立。
- `Orders.total_amount` 保留为受控冗余（报表快照），不拆分、不删除；由事务写入、回归校验。
- 不把 `Product` 与 `Inventory` 合并、不为 `category`/`role` 建字典表：均无传递依赖，拆分/合并不提升范式，只增加连接或锁竞争。

## 十三、复现步骤

1. 安装 SQL Server Express、SSMS 和 ODBC Driver 17（或 18）。
2. 按第七节顺序执行 `sql/01`—`sql/08`。
3. 执行 `sql/migration.sql`，再执行 `sql/09_app_accounts.sql`。
4. 执行 `sql/regression.sql`，确认输出 `REGRESSION PASS`。
5. 执行 `py scripts/validate_week5.py --output result/week5_validation.txt`，核对第5周数据验证结果。
6. 复制 `.env.example` 为 `.env`，填写三个应用账号密码。
7. 执行 `py scripts/create_test_db.py` 创建测试库。
8. 执行 `py -m pytest`，确认 63 项通过。
9. 需重新生成 ER 图时执行 `py docs/er/render_er.py`。

## 十四、常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `python` 退出码 49 | Windows 应用商店别名 | 改用 `py` |
| 受限账号执行 `NEXT VALUE FOR` 报 229 | 缺少序列 `UPDATE` 权限 | 重新执行 `sql/09_app_accounts.sql` |
| 插入订单明细报“不能插入计算列” | `subtotal` 是 PERSISTED 计算列 | INSERT 省略 `subtotal` |
| 返回的编号带空格 | `CHAR` 列尾部补空格 | 视图已 `RTRIM`；DAO 的 `row_to_dict` 也会 `rstrip` |
| 回滚后数据仍然存在 | 使用了 `with conn.cursor()`，pyodbc 退出时提交 | 使用 `dao.utils.cursor_scope(conn)` |
| `sqlcmd` 执行计算列脚本异常 | 未开启 QUOTED_IDENTIFIER | 加 `-I` |
| 测试连接失败 | `.env` 密码与 `09_app_accounts.sql` 不一致 | 核对三个应用账号密码 |

## 十五、Web 应用（成员B，应用侧）

成员B 在成员A 的 DAO 之上构建 Flask 应用，分层为：页面层（`app/routes/`）→ 业务层（`app/services/`）→ DAO（`dao/`，成员A）→ SQL Server。B 不写任何 SQL，只调用 DAO 公开接口。

### 15.1 启动

```bash
# 1. 安装依赖（含 Flask）
py -m pip install -r requirements.txt

# 2. 复制并填写 .env（复用成员A 三个受限账号的密码）
copy .env.example .env

# 3. 启动（项目根目录）
python run.py
# 或
flask --app run run
```

访问 `http://127.0.0.1:5000`，示例登录账号：

| 登录名 | 密码 | 角色 |
| --- | --- | --- |
| `manager` | `Manager@123` | 店长 |
| `clerk` | `Clerk@123` | 店员 |

### 15.2 角色界面

- 店员：商品/库存查看、开单、订单查询、会员办理与积分调整；
- 店长：在店员基础上，新增/编辑/停售商品、补货入库、员工管理、经营报表。

同一操作在业务层（`roles_required`）与数据库层（受限账号）各校验一次，形成双重防线。

### 15.3 统一异常与日志

- HTML 页面用 flash 展示友好文案；
- `Accept: application/json` 的请求返回统一 JSON：
  `{"ok": false, "code": "...", "message": "...", "data": null, "request_id": "..."}`；
- 后端日志写入 `logs/app.log`（已 gitignore），记录 `request_id`、时间、操作名称、用户角色、错误码、`detail` 与处理结果。

### 15.4 主要路由

| 路由 | 说明 | 权限 |
| --- | --- | --- |
| `/login` `/logout` | 登录 / 登出 | 公开 |
| `/` | 工作台 + 低库存预警 | 登录 |
| `/products` `/products/new` `/products/<id>/edit` `/products/<id>/status` | 商品查询/新增/编辑/停售 | 查询全员，写操作店长 |
| `/inventory` `/inventory/logs` `/inventory/<id>/adjust` | 库存、流水、补货入库 | 补货店长 |
| `/orders` `/orders/new` `/orders/<id>` `/orders/<id>/status` | 订单查询/开单/详情/改状态 | 登录 |
| `/members` `/members/new` `/members/<id>/edit` `/members/<id>/points` | 会员管理 | 登录 |
| `/employees` | 员工列表 | 店长 |
| `/reports` | 商品销售、库存状态、会员消费 | 店长 |
