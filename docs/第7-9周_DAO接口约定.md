# 第7—9周 DAO 接口约定（v1.0）

> 适用阶段：第二阶段第7—9周（Web 应用开发）
> 依据：《第7-9周任务讲解》《第7-9周分工计划（成员A/B）》《第五周任务讲解》《第六周任务讲解》
> 成员A：数据侧（ER/规范化/迁移、DAO、数据库受限账户、集成测试）
> 成员B：应用侧（Flask 骨架、页面层、业务层、统一异常、角色界面）
>
> **状态：v1.0 已定稿并实现。** `sql/migration.sql` 已落地；`dao/` 下 6 个 DAO 已按本文签名实现，`tests/` 下 63 项集成测试通过。字段名、类型、错误码、事务边界以本文为准；后续变更走文末变更记录。

---

## 0. 交接边界

A 与 B 的共同交接面只有一个：**DAO 契约**。A 实现 DAO，B 的业务层调用 DAO。页面层与业务层之间的接口属于 B 的内部实现，不在本文范围。

本文同时约定四类共同内容：

1. 数据库连接、事务与角色入口；
2. DAO 方法签名、入参、返回值与字段结构；
3. 统一错误码及 SQL Server 错误翻译规则；
4. 支撑这些接口所必需的数据库权限、视图和登录账号。

分层调用关系：

```
页面层（B） → 业务层（B） → 数据访问层 DAO（A） → SQL Server（A 维护）
```

约束：

- B 不写任何 SQL；A 不返回 pyodbc cursor/row。
- 所有用户输入必须通过参数化查询传入，禁止字符串拼接 SQL。
- 业务规则判断在 B 的业务层；库存是否充足等必须在事务内最终校验的规则，由 A 的 DAO 原子执行并抛出统一错误。
- 角色权限在 B 的业务层检查一次，数据库受限账户再检查一次，形成双重防线。

---

## 1. 契约总则

### 1.1 技术栈

- Python 3.x
- Flask
- pyodbc
- SQL Server

### 1.2 返回数据结构

- DAO 返回 `dict`、`list[dict]` 或 `Page`。
- 字段名与数据库列名一致，统一使用 `snake_case`。
- 金额使用 `Decimal`，时间使用 `datetime` / `date`；B 负责序列化为 JSON 或页面显示格式，A 不返回 `float`。
- 查不到返回 `None`。
- 列表返回 `Page`。
- 写操作返回写入/更新后的行；删除返回 `bool`。

### 1.3 连接与参数

- 所有 DAO 方法第一个参数为 `conn`，由 B 传入。
- **DAO 内部不 commit、不 rollback、不关闭连接。**
- 所有用户输入参数化；LIKE 关键字由 DAO 转义，B 直接传原值。
- 排序列、排序方向等动态部分由 DAO 内部白名单映射，B 不得传列名或 SQL 片段。

### 1.4 主键生成

- 主键由 A 的 DAO 生成，并在 `create_*` 的返回值中给出。
- B 不生成、不传入主键。
- 生成策略：v1.0 为 9 张表各建一个 SQL Server `SEQUENCE`，DAO 在事务内执行 `SELECT NEXT VALUE FOR dbo.SEQ_*`，按 `P+7位`、`O+11位` 等格式组装 `CHAR` 主码。
- 受限账号必须拥有对应序列对象的 `UPDATE` 权限（`GRANT UPDATE ON OBJECT::dbo.SEQ_*`），否则 `NEXT VALUE FOR` 报 229。

### 1.5 公共类型

```python
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterator, Literal, Sequence
from pyodbc import Connection

Role = Literal["clerk", "manager"]

@dataclass(frozen=True)
class Page:
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int

@dataclass(frozen=True)
class OrderItemInput:
    product_id: str
    quantity: int
```

分页约定：

- `page >= 1`；
- `page_size` 默认 20，上限 100；
- 非法分页参数抛 `VALIDATION_ERROR`；
- 固定排序：
  - 商品：`product_id`
  - 订单：`order_time DESC, order_id DESC`
  - 库存：`product_id`
  - 日志：`change_time DESC`

---

## 2. 连接、事务与配置

### 2.1 连接与事务入口

```python
# dao/database.py
class Database:
    def __init__(self, config: "DbConfig") -> None: ...

    @contextmanager
    def read(self, role: Role) -> Iterator[Connection]: ...
    # 只读连接；autocommit=True；退出时关闭

    @contextmanager
    def auth_read(self) -> Iterator[Connection]: ...
    # 登录专用连接，使用独立 auth 账号
    # 不能复用 clerk/manager 账号，原因见第 7 节

    @contextmanager
    def transaction(self, role: Role) -> Iterator[Connection]: ...
    # autocommit=False；正常退出 commit；异常 rollback；最后关闭
    # 不支持嵌套；检测到嵌套直接抛 TransactionStateError

    def ping(self, role: Role) -> bool: ...
```

B 的典型用法：

```python
# 查询
with db.read("clerk") as conn:
    page = product_dao.list(conn, keyword=kw, page=1)

# 写操作：事务边界在 B 的 service
with db.transaction("clerk") as conn:
    order = order_dao.create_with_details(conn, ...)
```

### 2.2 事务边界归属

**已确认：事务边界由 B 的业务层负责，A 的 DAO 一律不 commit。**

理由：任务书要求“业务层负责业务规则、事务边界和角色可执行范围”。分工计划中“`create_order_with_details()` 内部走事务”的表述按以下口径执行：

> `create_order_with_details()` 必须在 B 的 `db.transaction()` 内调用；方法内部只执行 SQL，不 commit、不 rollback、不关闭连接。

否则 B 再包一层事务会出现嵌套提交或提前提交。`Database.transaction()` 已实现嵌套检测，检测到嵌套直接抛 `TransactionStateError`。

### 2.3 配置项

B 的 `config.py` 按以下键读取，A 的 `Database` 消费。连接信息不得写死在页面或业务代码中。

```text
DB_DRIVER
DB_SERVER
DB_NAME
DB_AUTH_USER / DB_AUTH_PASSWORD
DB_CLERK_USER / DB_CLERK_PASSWORD
DB_MANAGER_USER / DB_MANAGER_PASSWORD
```

建议：

- `DB_DRIVER` 使用 `ODBC Driver 17 for SQL Server`（或 18，填本机已安装的驱动）；
- 本地开发可在连接串中加 `TrustServerCertificate=yes`；
- 密码通过环境变量或 `.env` 注入，`.env` 不提交仓库；
- A 提供 `.env.example`，B 负责读取。

---

## 3. 统一错误契约

### 3.1 异常类型

A 的 DAO 只抛 `DAOError`，B 统一转换为 HTTP 响应。A 不得向前端返回原始 SQL、连接串、服务器路径或异常堆栈。

```python
class DAOError(Exception):
    code: str
    message: str                 # 可给用户看的简短提示
    context: dict[str, Any] | None = None   # 结构化信息，如库存不足的数量
    detail: str | None = None    # 只进日志，不给前端
    retryable: bool = False
```

### 3.2 共享错误码

| code | 主要抛出方 | B 的 HTTP | 典型场景 |
| --- | --- | --- | --- |
| `VALIDATION_ERROR` | B（主）/ A（类型、长度） | 400 | 必填、格式、范围、分页参数 |
| `UNAUTHENTICATED` | B | 401 | 未登录、会话过期 |
| `FORBIDDEN` | B | 403 | 店员删商品、查看员工 |
| `NOT_FOUND` | B（由 `None` 转） | 404 | 商品/订单/会员不存在 |
| `BUSINESS_RULE_VIOLATION` | B / A | 409 | 库存不足、停售商品下单、数量 ≤ 0 |
| `CONFLICT_UNIQUE` | A | 409 | 手机号重复、库存行重复 |
| `CONFLICT_FOREIGN_KEY` | A | 409 | 删除被订单引用的商品、无效会员 |
| `CONFLICT_CHECK` | A | 409 | CHECK 约束（负库存、非法状态） |
| `DB_UNAVAILABLE` | A | 503 | 连接失败、登录失败、库不存在 |
| `DB_TIMEOUT` | A | 503 | 查询超时、死锁重试耗尽 |
| `TRANSACTION_FAILED` | A / B | 500 | commit/rollback 失败 |
| `INTERNAL_ERROR` | B | 500 | 未分类异常 |

### 3.3 SQL Server 错误翻译

A 在 DAO 内负责把 pyodbc / SQL Server 原生错误翻译为统一错误码，至少覆盖：

| SQL Server 错误号 | 统一错误码 | 说明 |
| --- | --- | --- |
| `2627` / `2601` | `CONFLICT_UNIQUE` | 主键/唯一约束冲突 |
| `547` | `CONFLICT_FOREIGN_KEY` 或 `CONFLICT_CHECK` | 根据消息内容区分外码/CHECK |
| `515` | `VALIDATION_ERROR` | 非空列插入 NULL |
| `245` / `8114` / `8115` | `VALIDATION_ERROR` | 类型转换失败 |
| `2628` / `8152` | `VALIDATION_ERROR` | 字符串截断 |
| `229` / `230` | `FORBIDDEN` | 数据库对象权限不足 |
| `1205` | `DB_TIMEOUT`，`retryable=True` | 死锁 |
| `-2` / `HYT00` | `DB_TIMEOUT` | 查询超时 |
| `18456` / `4060` / `08001` / `08S01` / `28000` | `DB_UNAVAILABLE` | 登录失败、库不存在、网络失败 |
| `208` / `207` / `2812` | `INTERNAL_ERROR` | 表/列/存储过程不存在，只记日志 |

注意：

- `detail` 保存原始错误文本，只写后端日志；
- `message` 使用统一友好文案；
- `context` 可携带结构化数据，例如：

```python
DAOError(
    code="BUSINESS_RULE_VIOLATION",
    message="库存不足",
    context={"product_id": "P001", "available": 2, "requested": 3},
)
```

### 3.4 统一响应格式（B 实现）

```json
{
  "ok": false,
  "code": "BUSINESS_RULE_VIOLATION",
  "message": "库存不足",
  "data": null,
  "request_id": "..."
}
```

HTML 页面可用 flash 消息展示 `message`；后端日志同时记录 `request_id`、时间、操作名称、用户角色、错误码、`detail` 和处理结果。

---

## 4. 数据行结构

以下为 DAO 返回值中的字段约定。金额均为 `Decimal`，时间为 `datetime` / `date`。

### 4.1 商品行

```python
{
    "product_id": str,
    "product_name": str,
    "category": str | None,
    "price": Decimal,
    "stock_warn": int,
    "status": str,          # 在售 / 停售
}
```

### 4.2 库存行

```python
{
    "inventory_id": str,
    "product_id": str,
    "product_name": str,
    "quantity": int,
    "stock_warn": int,
    "stock_status": str,    # 缺货 / 库存不足 / 正常
    "update_time": datetime,
}
```

### 4.3 订单表头行

```python
{
    "order_id": str,
    "member_id": str | None,
    "member_name": str,          # 散客时由 SQL 返回“散客”
    "employee_id": str,
    "employee_name": str,
    "order_type": str,
    "order_time": datetime,
    "total_amount": Decimal,
    "pay_method": str,
    "order_status": str,
}
```

### 4.4 订单明细行

```python
{
    "detail_id": str,
    "order_id": str,
    "product_id": str,
    "product_name": str,
    "quantity": int,
    "unit_price": Decimal,
    "subtotal": Decimal,
}
```

### 4.5 会员行

```python
{
    "member_id": str,
    "member_name": str,
    "phone": str,
    "points": int,
    "join_date": date,
}
```

### 4.6 员工行

```python
{
    "employee_id": str,
    "employee_name": str,
    "role": str,            # 店长 / 店员
    "phone": str | None,
    "hire_date": date,
}
```

### 4.7 登录凭据行

```python
{
    "employee_id": str,
    "employee_name": str,
    "role": str,            # 店长 / 店员
    "login_name": str,
    "password_hash": str,
    "is_active": bool,
}
```

> `login_name`、`password_hash`、`is_active` 在 v0.1 中不存在，需在 v1.0 迁移中补充，见第 8 节。

---

## 5. DAO 接口清单

### 5.1 ProductDAO

```python
class ProductDAO:
    def list(
        self, conn,
        *,
        keyword: str | None = None,
        category: str | None = None,
        status: Literal["在售", "停售"] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page: ...

    def get(self, conn, product_id: str) -> dict | None: ...

    def create(
        self, conn,
        *,
        product_name: str,
        category: str | None,
        price: Decimal,
        stock_warn: int = 10,
        status: Literal["在售", "停售"] = "在售",
    ) -> dict: ...
    # 必须在 db.transaction(...) 内调用（主码来自 SEQUENCE）
    # 只插 Product；库存行由 B 在同一事务里调用 InventoryDAO.create

    def update(
        self, conn, product_id: str, changes: dict[str, Any]
    ) -> dict | None: ...
    # changes 只允许 product_name/category/price/stock_warn/status
    # 未知键抛 VALIDATION_ERROR；返回 None 表示商品不存在

    def set_status(
        self, conn, product_id: str, status: Literal["在售", "停售"]
    ) -> dict | None: ...

    def delete(self, conn, product_id: str) -> bool: ...
    # 被 OrderDetail/Inventory 引用时抛 CONFLICT_FOREIGN_KEY
    # 界面优先引导“停售”，不要物理删除

    def list_categories(self, conn) -> list[str]: ...
```

### 5.2 InventoryDAO

```python
class InventoryDAO:
    def get(self, conn, product_id: str) -> dict | None: ...

    def list(
        self, conn,
        *,
        keyword: str | None = None,
        low_stock_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> Page: ...
    # keyword 匹配 product_id / product_name

    def create(
        self, conn,
        *,
        product_id: str,
        quantity: int = 0,
        remark: str | None = None,
    ) -> dict: ...
    # 必须在 db.transaction(...) 内调用
    # 插入 Inventory；quantity != 0 时同时写一条“入库”日志
    # 同一商品重复创建会触发 CONFLICT_UNIQUE

    def adjust(
        self, conn, product_id: str,
        *,
        change_qty: int,
        change_type: Literal["入库", "销售"],
        remark: str | None = None,
    ) -> dict: ...
    # 必须在 db.transaction(...) 内调用
    # change_qty 带符号：入库为正，销售为负；0 抛 VALIDATION_ERROR
    # 类型与符号不匹配抛 VALIDATION_ERROR
    # 扣减后为负抛 BUSINESS_RULE_VIOLATION
    # 返回 quantity_before / quantity_after / log_id

    def set_warn(self, conn, product_id: str, stock_warn: int) -> dict | None: ...

    def list_logs(
        self, conn,
        *,
        product_id: str | None = None,
        change_type: Literal["入库", "销售"] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page: ...
```

`adjust` 必须使用原子 SQL，不得先查后改：

```sql
UPDATE Inventory
SET quantity = quantity + ?, update_time = GETDATE()
WHERE product_id = ? AND quantity + ? >= 0;
```

`rowcount == 0` 时再区分：商品不存在 → `NOT_FOUND`；库存不足 → `BUSINESS_RULE_VIOLATION`。

### 5.3 OrderDAO

```python
class OrderDAO:
    def create_with_details(
        self, conn,
        *,
        member_id: str | None,
        employee_id: str,
        pay_method: Literal["现金", "微信", "支付宝"],
        items: Sequence[OrderItemInput],
        order_type: Literal["商品", "服务"] = "商品",
        order_status: Literal["已完成", "未完成"] = "已完成",
    ) -> dict: ...

    def get(
        self, conn, order_id: str, *, include_details: bool = True
    ) -> dict | None: ...

    def list(
        self, conn,
        *,
        keyword: str | None = None,
        member_id: str | None = None,
        employee_id: str | None = None,
        order_status: Literal["已完成", "未完成"] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page: ...

    def update_status(
        self, conn, order_id: str, status: Literal["已完成", "未完成"]
    ) -> dict | None: ...

    def list_details(self, conn, order_id: str) -> list[dict]: ...
```

`create_with_details` 必须在**同一个事务**内完成：

1. 校验 `items` 非空、数量 > 0；
2. 同一商品重复出现时按 `product_id` 合并数量（第五周提示明确说不能假设一单只出现一次商品）；
3. 按 `product_id` 排序后使用 `SELECT ... WITH (UPDLOCK, ROWLOCK)` 锁定库存行，统一检查商品存在、状态为“在售”、库存足够；
4. 从 `Product.price` 读取单价，**不接受 B 传价格**；
5. 写 `Orders`，`total_amount = Σ(quantity × unit_price)`，四舍五入 2 位；
6. 写 `OrderDetail`，`subtotal = quantity × unit_price`；
7. 扣减 `Inventory`；
8. 每条明细写 `InventoryLog`：`change_type='销售'`、`change_qty=-quantity`；
9. 任一步失败，B 的事务整体回滚。

返回结构：

```python
{
    "order_id": str,
    "member_id": str | None,
    "member_name": str,
    "employee_id": str,
    "employee_name": str,
    "order_type": str,
    "order_time": datetime,
    "total_amount": Decimal,
    "pay_method": str,
    "order_status": str,
    "details": [
        {
            "detail_id": str,
            "product_id": str,
            "product_name": str,
            "quantity": int,
            "unit_price": Decimal,
            "subtotal": Decimal,
        }
    ],
}
```

订单列表返回表头行，不展开明细；`get()` 才带 `details`。

### 5.4 MemberDAO

```python
class MemberDAO:
    def search(
        self, conn,
        *,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page: ...
    # keyword 匹配 member_id / member_name / phone

    def get(self, conn, member_id: str) -> dict | None: ...

    def create(
        self, conn,
        *,
        member_name: str,
        phone: str,
        points: int = 0,
    ) -> dict: ...
    # 必须在 db.transaction(...) 内调用（主码来自 SEQUENCE）

    def update(
        self, conn, member_id: str, changes: dict[str, Any]
    ) -> dict | None: ...
    # changes 只允许 member_name/phone/points

    def add_points(self, conn, member_id: str, delta: int) -> dict | None: ...
```

手机号唯一冲突由 A 翻译为 `CONFLICT_UNIQUE`，B 显示“手机号已存在”。

### 5.5 EmployeeDAO / 登录

```python
class EmployeeDAO:
    def get_credentials(self, conn, login_name: str) -> dict | None: ...
    # 只能用 db.auth_read() 的 conn 调用
    # 返回 employee_id, employee_name, role, login_name,
    #      password_hash, is_active

    def get(self, conn, employee_id: str) -> dict | None: ...

    def list(self, conn) -> list[dict]: ...
    # 店长专用；店员连接查询会因权限失败
```

密码校验放在 B 的业务层（werkzeug 的 `check_password_hash`），A 只返回 hash，不返回明文。登录成功后 B 将 `employee_id`、`role` 放入 Flask session；后续按角色选择 `db.read("clerk")` 或 `db.read("manager")`。

v1.0 已通过 `sql/migration.sql` 补齐 `login_name`、`password_hash`、`is_active`，并建立 `v_employee_login`；`EmployeeDAO.get_credentials` 已实现。样例账号为 `manager / Manager@123`、`clerk / Clerk@123`。

### 5.6 ReportDAO（可选）

```python
class ReportDAO:
    def product_sales(
        self, conn, *, start: datetime | None = None,
        end: datetime | None = None, limit: int | None = None,
    ) -> list[dict]: ...

    def inventory_status(
        self, conn, *, low_stock_only: bool = False
    ) -> list[dict]: ...

    def member_consumption(
        self, conn, *, member_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict]: ...
```

直接查询 `v_product_sales`、`v_inventory_status`、`v_member_consumption`，不要重写统计 SQL。`ReportDAO` 已实现三个方法；统计页不是 7—9 周核心功能，B 暂不做则可不调用。

### 5.7 PetService / ServiceAppointment（P2，暂缓）

7—9 周核心对象是商品、库存、订单、订单明细。若 B 保留服务预约页，再补充：

```python
class ServiceDAO:
    def list(self, conn, *, status=None, page=1, page_size=20) -> Page: ...
    def get(self, conn, service_id: str) -> dict | None: ...
    def create(self, conn, **fields) -> dict: ...
    def update(self, conn, service_id: str, changes: dict) -> dict | None: ...
    def delete(self, conn, service_id: str) -> bool: ...

class AppointmentDAO:
    def list(self, conn, *, member_id=None, employee_id=None,
             status=None, start=None, end=None,
             page=1, page_size=20) -> Page: ...
    def get(self, conn, appointment_id: str) -> dict | None: ...
    def create(self, conn, *, member_id, service_id, employee_id,
               appoint_time, remark=None) -> dict: ...
    def update_status(self, conn, appointment_id: str, status: str) -> dict | None: ...
```

建议先不实现，避免核心流程未打磨完就扩大范围。

---

## 6. 数据访问层实现约束

### 6.1 参数化与注入防护

- 所有值使用 `?` 占位符；
- 禁止 f-string、`%`、`+` 拼接用户输入；
- LIKE 查询由 DAO 转义 `%`、`_`、`[` 等通配符，并显式指定 `ESCAPE`；
- 排序字段、表名、列名不得来自用户输入，必须走白名单映射。

### 6.2 事务与并发

- `transaction()` 内 `autocommit=False`；
- 正常退出只 commit 一次；任何异常 rollback；
- 不支持嵌套事务；检测到嵌套直接抛错；
- 库存扣减使用 `UPDATE ... WHERE quantity + ? >= 0` 或在事务内 `WITH (UPDLOCK, ROWLOCK)`；
- 多商品下单按 `product_id` 排序加锁，降低死锁概率；
- 死锁或超时可在 `transaction()` 层重试，默认最多 2 次，仅对 `retryable=True` 的错误重试。

### 6.3 主键生成

- `create_*` 返回生成的主键；
- 具体策略见第 8 节；
- 生成过程必须在事务内完成，避免并发重复。

### 6.4 日志与审计

- A 的 DAO 不写应用日志文件，只抛 `DAOError`，由 B 的统一异常处理写日志；
- 若需要记录数据库层慢查询，可在 `Database` 内使用标准 `logging`，但不得记录明文密码；
- `InventoryLog` 当前没有操作人字段，审计信息不完整，见第 8 节。

---

## 7. 数据库权限、视图与登录账号

以下问题曾是 B 调用 DAO 时的数据库层阻塞项，现已在 v1.0 权限脚本中处理；保留记录便于复核。

### 7.1 `role_clerk` 缺少 `UPDATE Inventory`（已修复）

v0.1 的 `08_role.sql` 只授予 `SELECT ON Inventory`，但下单必须扣库存。`sql/09_app_accounts.sql` 已补：

```sql
GRANT UPDATE ON dbo.Inventory TO role_clerk;
```

`regression.sql` 第6.2节验证店员可以扣库存。

### 7.2 `role_clerk` 缺少 `SELECT Employee`（已用视图解决）

订单列表/详情如果直接 join `Employee`，店员查询会失败。v1.0 已新增订单表头视图 `v_order_header` 并授权：

```sql
CREATE VIEW dbo.v_order_header AS
SELECT o.order_id, o.member_id,
       ISNULL(m.member_name, '散客') AS member_name,
       o.employee_id, e.employee_name,
       o.order_type, o.order_time, o.total_amount,
       o.pay_method, o.order_status
FROM Orders o
JOIN Employee e ON o.employee_id = e.employee_id
LEFT JOIN Member m ON o.member_id = m.member_id;

GRANT SELECT ON dbo.v_order_header TO role_clerk;
```

现有视图也需要显式授权给店员。所有权链只在“已经有权访问视图”之后才生效，光有基表权限不够：

```sql
GRANT SELECT ON dbo.v_order_detail       TO role_clerk;
GRANT SELECT ON dbo.v_inventory_status   TO role_clerk;
GRANT SELECT ON dbo.v_product_sales      TO role_clerk;
GRANT SELECT ON dbo.v_member_consumption TO role_clerk;
GRANT SELECT ON dbo.v_service_appointment TO role_clerk;
```

### 7.3 `clerk_user` / `manager_user` 是 `WITHOUT LOGIN`（已另建登录）

它们只能配合 `EXECUTE AS` 做课堂演示，pyodbc 无法用它们登录。v1.0 已另建 SQL 登录并映射：

```sql
CREATE LOGIN petcare_clerk WITH PASSWORD = '...';
CREATE USER  petcare_clerk FOR LOGIN petcare_clerk;
ALTER ROLE role_clerk ADD MEMBER petcare_clerk;

CREATE LOGIN petcare_manager WITH PASSWORD = '...';
CREATE USER  petcare_manager FOR LOGIN petcare_manager;
ALTER ROLE role_manager ADD MEMBER petcare_manager;
```

原来的 `clerk_user` / `manager_user` 保留给 `08_role.sql` 的回归测试与课堂演示。

### 7.4 登录不能走 clerk/manager 连接（已用 auth 账号隔离）

`role_clerk` 看不到 `Employee`，因此 `auth_read()` 使用第三个独立账号，只授予一个窄视图：

```sql
CREATE VIEW dbo.v_employee_login AS
SELECT employee_id, login_name, password_hash, role, is_active
FROM dbo.Employee;

CREATE LOGIN petcare_auth WITH PASSWORD = '...';
CREATE USER  petcare_auth FOR LOGIN petcare_auth;
GRANT SELECT ON dbo.v_employee_login TO petcare_auth;
```

登录与业务连接彻底分开，符合最小权限原则。

### 7.5 权限对照表

| 操作 | 店员 `role_clerk` | 店长 `role_manager` | 应用连接 |
| --- | --- | --- | --- |
| 查询商品 | 有 | 有 | clerk / manager |
| 新增/修改/停售商品 | 无 | 有 | manager |
| 删除商品 | 无 | 有 | manager |
| 查询库存 | 有 | 有 | clerk / manager |
| 调整库存 | 有（v1.0 已补 `UPDATE`） | 有 | clerk / manager |
| 查询订单/明细 | 有 | 有 | clerk / manager |
| 新增订单/明细 | 有 | 有 | clerk / manager |
| 删除订单 | 无 | 有 | 建议应用层禁用 |
| 查询员工 | 无 | 有 | manager |
| 登录读取凭据 | 无 | 无 | auth |

---

## 8. 已确认决策（v1.0）

| 编号 | 问题 | 最终决定 | 落地位置 |
| --- | --- | --- | --- |
| 1 | v1.0 表结构 | 以 `sql/migration.sql` 为准；9 张表字段、视图、序列、索引已锁定 | `sql/migration.sql`、`tests/` |
| 2 | 登录凭据 | `Employee` 增加 `login_name`、`password_hash`、`is_active`；`petcare_auth` 只读 `v_employee_login` | `sql/migration.sql`、`sql/09_app_accounts.sql` |
| 3 | 事务边界 | B 的业务层负责；DAO 只使用传入 `conn`，不 commit/rollback/close；嵌套事务直接报错 | `dao/database.py`、`dao/utils.py` |
| 4 | 主键生成 | 9 个 `SEQUENCE` + `NEXT VALUE FOR`；DAO 在事务内生成并返回主码 | `sql/migration.sql`、`dao/ids.py` |
| 5 | 库存日志类型 | v1.0 仍只用“入库/销售”；“调整/盘点”和 `operator_id` 列入 v1.1，不阻塞本周接口 | `dao/inventory_dao.py` |
| 6 | 订单状态与删除 | 应用只创建“已完成/未完成”订单，不做物理删除；取消状态列入 v1.1 | `dao/order_dao.py` |
| 7 | 角色口径 | 只保留“店员（clerk）”和“店长（manager）”；顾客端不单独建角色，散客通过订单 `member_id = NULL` 表达 | `dao/config.py`、`sql/09_app_accounts.sql` |
| 8 | 折扣/积分 | 不做折扣；成交单价取 `Product.price` 当前值并写入 `OrderDetail.unit_price` 快照；积分只做加减，不参与订单金额 | `dao/order_dao.py`、`dao/member_dao.py` |

### 8.1 关于 `Orders.order_type`

`Orders.order_type` 数据库仍允许“商品/服务”，但 v1.0 的应用只写“商品”。服务预约走独立的 `ServiceAppointment` 表，不混入商品订单。若后续要做“服务订单”，需要新增服务订单明细表，不能在 `OrderDetail` 中塞 `service_id`。

### 8.2 关于 `Product.category`

v1.0 **不拆分** `Category` 表。`ProductDAO` 的返回字段保持：

```python
{"product_id": str, "product_name": str, "category": str | None,
 "price": Decimal, "stock_warn": int, "status": str}
```

`create/update` 的 `category` 仍为字符串。类别字典化列入 v1.1；届时再引入 `category_id`，不在本周破坏 B 的页面字段。

### 8.3 关于 `OrderDetail.subtotal`

v1.0 的 `subtotal` 是 `PERSISTED` 计算列。B/DAO 的插入语句必须**省略** `subtotal`；显式写入会报“不能插入计算列”。`OrderDAO.create_with_details` 已按此实现。

---

## 9. 联调验收用例（v1.0 已覆盖）

接口定完后，A/B 一起跑以下用例，作为“接口真正对齐”的标准。A 侧集成测试的对应关系见本节末尾。

1. 正确账号登录成功；错误密码、禁用账号失败；返回角色正确。
2. 店员删除商品、查看员工列表被拒（B 返回 403，数据库权限也拒绝）。
3. 店长可以新增/修改/停售商品、查看员工。
4. 新增商品 + 创建库存行在同一事务；库存行重复时商品也回滚。
5. 入库、销售调整正确；扣成负数被拒；每次调整都有日志。
6. 两件商品下单：订单、两条明细、总金额、库存扣减、两条销售日志全部正确。
7. 第二件商品库存不足：订单、明细、第一件库存、日志全部回滚，不能只扣一半。
8. 同一商品在 `items` 里出现两次：数量合并后校验库存，不超卖。
9. 关键字传 `' OR 1=1 --`：按普通字符串查询，不返回全表。
10. 数据库停掉/连接串错误：前端看到统一友好提示，后端日志有 `request_id`、错误码和原始错误。

A 侧对应的自动化验证：

| 验收项 | 测试文件/用例 | 结果 |
| --- | --- | --- |
| 1 登录账号与角色 | `tests/test_employee_dao.py`、`tests/test_database.py::test_ping_all_roles` | PASS |
| 2 店员越权被拒 | `tests/test_permissions.py`、`tests/test_product_dao.py::test_clerk_cannot_create_product` | PASS |
| 3 店长商品/员工权限 | `tests/test_permissions.py`、`tests/test_employee_dao.py::test_manager_can_list_employees` | PASS |
| 4 商品 + 库存同事务 | `tests/test_inventory_dao.py::test_create_writes_initial_log`、`tests/conftest.py::product_factory` | PASS |
| 5 库存调整与日志 | `tests/test_inventory_dao.py` | PASS |
| 6 两商品下单 | `tests/test_order_dao.py::test_create_order_merges_duplicate_items` | PASS |
| 7 库存不足整单回滚 | `tests/test_order_dao.py::test_insufficient_stock_aborts_before_writes` | PASS |
| 8 重复商品合并 | `tests/test_order_dao.py::test_create_order_merges_duplicate_items` | PASS |
| 9 SQL 注入字符串 | `tests/test_product_dao.py::test_keyword_is_parameterized` 等 | PASS |
| 10 数据库不可用 | `Database.ping` 覆盖正常路径；断库场景需 B 做页面级验证 | 部分 |

---

## 10. 变更记录

| 日期 | 版本 | 修改人 | 说明 |
| --- | --- | --- | --- |
| 2026-11-07 | v0.1 | 成员A | 初稿：按 v0.1 表结构整理 DAO 契约、错误码、权限阻塞项与待确认问题 |
| 2026-11-08 | v1.0 | 成员A | 定稿：按 `migration.sql` 锁定字段；确认事务边界、序列主键、登录视图、受限账号；补充实现状态与测试映射 |

### 10.1 v1.0 相对草案的变更摘要

1. `OrderDetail.subtotal` 改为 `PERSISTED` 计算列，插入时省略；
2. `Employee` 增加 `login_name`、`password_hash`、`is_active`，新增 `v_employee_login`；
3. 新增 `v_order_header`，店员通过视图读取员工姓名；
4. 主键改为 9 个 `SEQUENCE`，受限账号补序列 `UPDATE` 权限；
5. 事务边界确定为 B 负责，DAO 不 commit；
6. 库存日志暂不增加“调整/盘点”和 `operator_id`；
7. `Product.category` 保留字符串，不拆 `Category` 表；
8. 角色只保留 clerk/manager，散客用 `member_id = NULL` 表达。
