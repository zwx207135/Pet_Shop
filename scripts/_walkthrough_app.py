"""Task A: real HTTP walkthrough against the running Flask app + PetCareDB.

Uses a cookie-enabled HTTP client (requests.Session) to exercise the clerk and
manager flows, and verifies DB side effects with the manager restricted account.
"""

from __future__ import annotations

import re
import sys
import time

import requests

BASE = "http://127.0.0.1:5000"

# --- read-only DB check helper (uses restricted manager account from .env) ---
from dao import DbConfig, Database, ErrorCode, DAOError

cfg = DbConfig.from_env()
db = Database(cfg)

_step = 0


def step(title: str) -> None:
    global _step
    _step += 1
    print(f"\n=== [{_step}] {title} ===")


def show(resp, *, limit: int = 400) -> None:
    print(f"  HTTP {resp.status_code}")
    loc = resp.headers.get("Location")
    if loc:
        print(f"  -> redirect: {loc}")
    text = resp.text
    # surface flash messages and key markers
    for marker in ("flash-danger", "flash-success", "flash-info", "error-msg"):
        for m in re.findall(r'class="[^"]*' + re.escape(marker) + r'[^"]*">([^<]*)', text):
            m = m.strip()
            if m:
                print(f"  [flash] {m}")


def db_scalar(sql: str, params=()):
    with db.read("manager") as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None


def db_rows(sql: str, params=()):
    with db.read("manager") as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = []
        for r in cur.fetchall():
            d = {}
            for c, v in zip(cols, r):
                d[c] = v.rstrip() if isinstance(v, str) else v
            rows.append(d)
        return rows


def main() -> int:
    # ---------------------------------------------------------------
    step("未登录访问受保护页面 -> 重定向到登录页")
    s = requests.Session()
    r = s.get(BASE + "/orders", allow_redirects=False)
    show(r)
    assert r.status_code == 302 and "/login" in (r.headers.get("Location") or "")

    # ---------------------------------------------------------------
    step("店员登录（clerk / Clerk@123）")
    r = s.post(BASE + "/login", data={"login_name": "clerk", "password": "Clerk@123"}, allow_redirects=False)
    show(r)
    assert r.status_code == 302 and r.headers["Location"].endswith("/")

    step("店员登录后工作台（低库存预警）")
    r = s.get(BASE + "/")
    show(r)
    assert "赵店员" in r.text and "店员" in r.text
    m = re.findall(r"剩余 (\d+) 件", r.text)
    print(f"  低库存预警条数: {len(m)}")

    # ---------------------------------------------------------------
    step("错误密码登录 -> 401 + 友好提示")
    s_bad = requests.Session()
    r = s_bad.post(BASE + "/login", data={"login_name": "clerk", "password": "wrong"}, allow_redirects=False)
    show(r)
    assert r.status_code == 401

    step("不存在的账号登录 -> 401")
    s_bad2 = requests.Session()
    r = s_bad2.post(BASE + "/login", data={"login_name": "nobody", "password": "x"}, allow_redirects=False)
    show(r)
    assert r.status_code == 401

    # ---------------------------------------------------------------
    step("店员：商品列表 + 关键字筛选（'猫粮'）")
    r = s.get(BASE + "/products", params={"q": "猫粮"})
    show(r)
    assert "皇家猫粮" in r.text

    step("店员：商品列表分页")
    r = s.get(BASE + "/products", params={"page": 1})
    show(r)
    assert "皇家猫粮" in r.text and "狗狗磨牙棒" in r.text  # 仅3条样例，未触发多页；分页逻辑由 DAO 测试覆盖

    step("店员：库存查询 + 流水查看")
    r = s.get(BASE + "/inventory")
    show(r)
    r = s.get(BASE + "/inventory/logs")
    show(r)
    assert "流水" in r.text or "日志" in r.text or "InventoryLog" in r.text or r.status_code == 200

    # ---------------------------------------------------------------
    step("店员：开单（P001×2 + P002×1 + P002×2 -> 重复合并 P001×2, P002×3）")
    before_inv = db_rows(
        "SELECT product_id, quantity FROM dbo.Inventory WHERE product_id IN ('P001','P002') ORDER BY product_id"
    )
    print(f"  开单前库存: {before_inv}")
    r = s.post(
        BASE + "/orders/new",
        data={
            "member_id": "M001",
            "pay_method": "微信",
            "product_id": ["P001", "P002", "P002"],
            "quantity": ["2", "1", "2"],
        },
        allow_redirects=False,
    )
    show(r)
    assert r.status_code == 302
    detail_url = r.headers["Location"]
    print(f"  订单详情地址: {detail_url}")

    step("店员：查看新订单详情（金额/明细/合并）")
    r = s.get(BASE + detail_url)
    show(r)
    order_id = detail_url.rsplit("/", 1)[-1]
    # total amount shown on page
    total_m = re.search(r"¥([0-9,]+\.\d{2})", r.text)
    print(f"  页面总金额: {total_m.group(1) if total_m else 'N/A'}")
    assert order_id.startswith("O")

    step("DB 核对：订单总额 = 明细合计 + 库存扣减 + 销售流水")
    header = db_rows("SELECT order_id, total_amount FROM dbo.Orders WHERE order_id = ?", [order_id])
    details = db_rows("SELECT product_id, quantity, unit_price, subtotal FROM dbo.OrderDetail WHERE order_id = ? ORDER BY product_id", [order_id])
    logs = db_rows("SELECT product_id, change_type, change_qty FROM dbo.InventoryLog WHERE remark = ? ORDER BY product_id", [f"订单{order_id}"])
    print(f"  订单头: {header}")
    for d in details:
        print(f"  明细: {d}")
    print(f"  销售流水: {logs}")
    db_total = float(header[0]["total_amount"])
    sum_details = float(sum(d["subtotal"] for d in details))
    assert abs(db_total - sum_details) < 0.001, "total != sum(details)"
    # merged quantities: P001×2, P002×3
    merged = {d["product_id"]: d["quantity"] for d in details}
    assert merged == {"P001": 2, "P002": 3}, f"merge mismatch: {merged}"
    after_inv = db_rows(
        "SELECT product_id, quantity FROM dbo.Inventory WHERE product_id IN ('P001','P002') ORDER BY product_id"
    )
    print(f"  开单后库存: {after_inv}")
    for b, a in zip(before_inv, after_inv):
        expect = b["quantity"] - merged[b["product_id"]]
        assert a["quantity"] == expect, f"stock wrong for {b['product_id']}"
    assert len(logs) == 2  # one per merged line

    step("店员：订单列表 + 订单查询")
    r = s.get(BASE + "/orders")
    show(r)
    assert order_id in r.text

    # ---------------------------------------------------------------
    step("店员：会员办理 -> 修改资料 -> 积分调整")
    phone = "138" + str(int(time.time()))[-8:]
    r = s.post(
        BASE + "/members/new",
        data={"member_name": "联调测试会员", "phone": phone, "points": "0"},
        allow_redirects=False,
    )
    show(r)
    assert r.status_code == 302
    new_member = db_scalar("SELECT member_id FROM dbo.Member WHERE phone = ?", [phone])
    print(f"  新会员编号: {new_member}")
    r = s.post(
        BASE + f"/members/{new_member}/edit",
        data={"member_name": "联调测试会员改", "phone": phone, "points": "10"},
        allow_redirects=False,
    )
    show(r)
    assert r.status_code == 302
    r = s.post(BASE + f"/members/{new_member}/points", data={"delta": "20"}, allow_redirects=False)
    show(r)
    pts = db_scalar("SELECT points FROM dbo.Member WHERE member_id = ?", [new_member])
    print(f"  最终积分: {pts}")
    assert pts == 30

    # ---------------------------------------------------------------
    step("权限：店员访问店长专属路由 -> 302 重定向 + 友好提示")
    for url in ("/employees", "/reports", "/products/new", "/inventory/P001/adjust"):
        r = s.get(BASE + url, allow_redirects=False)
        show(r)
        assert r.status_code == 302 and r.headers["Location"].endswith("/"), f"{url} not blocked"

    step("权限：店员提交店长写操作（POST 新建商品）-> 仍被拦截")
    r = s.post(BASE + "/products/new", data={"product_name": "越权商品", "price": "1", "quantity": "1"}, allow_redirects=False)
    show(r)
    assert r.status_code == 302  # roles_required blocks before DAO

    step("店员登出")
    s.post(BASE + "/logout", allow_redirects=False)

    # ---------------------------------------------------------------
    step("店长登录（manager / Manager@123）")
    s2 = requests.Session()
    r = s2.post(BASE + "/login", data={"login_name": "manager", "password": "Manager@123"}, allow_redirects=False)
    show(r)
    assert r.status_code == 302

    step("店长工作台（导航含 员工/报表）")
    r = s2.get(BASE + "/")
    show(r)
    assert "王店长" in r.text and "店长" in r.text
    assert "员工" in r.text and "报表" in r.text

    step("店长：新增商品（自动建初始库存）")
    prod_name = "联调测试猫砂" + str(int(time.time()))[-6:]
    r = s2.post(
        BASE + "/products/new",
        data={"product_name": prod_name, "category": "用品", "price": "39.90", "stock_warn": "5", "status": "在售", "quantity": "30"},
        allow_redirects=False,
    )
    show(r)
    assert r.status_code == 302
    np = db_rows("SELECT p.product_id, p.product_name, p.price, p.status, i.quantity FROM dbo.Product p LEFT JOIN dbo.Inventory i ON i.product_id=p.product_id WHERE p.product_name=?", [prod_name])
    print(f"  新商品: {np}")
    new_pid = np[0]["product_id"]
    assert np[0]["quantity"] == 30

    step("店长：编辑商品（改价）")
    r = s2.post(BASE + f"/products/{new_pid}/edit", data={"product_name": prod_name, "category": "用品", "price": "45.00", "stock_warn": "5", "status": "在售"}, allow_redirects=False)
    show(r)
    assert r.status_code == 302
    assert db_scalar("SELECT price FROM dbo.Product WHERE product_id = ?", [new_pid]) == 45.0

    step("店长：补货入库（+20）")
    before_qty = db_scalar("SELECT quantity FROM dbo.Inventory WHERE product_id = ?", [new_pid])
    r = s2.post(BASE + f"/inventory/{new_pid}/adjust", data={"change_qty": "20", "remark": "联调补货"}, allow_redirects=False)
    show(r)
    assert r.status_code == 302
    after_qty = db_scalar("SELECT quantity FROM dbo.Inventory WHERE product_id = ?", [new_pid])
    print(f"  补货前 {before_qty} -> 补货后 {after_qty}")
    assert after_qty == before_qty + 20

    step("店长：停售商品")
    r = s2.post(BASE + f"/products/{new_pid}/status", data={"status": "停售"}, allow_redirects=False)
    show(r)
    assert r.status_code == 302
    assert db_scalar("SELECT status FROM dbo.Product WHERE product_id = ?", [new_pid]) == "停售"

    step("店长：新增低库存商品（预警演示，qty=2 < warn=10）")
    if db_scalar("SELECT COUNT(*) FROM dbo.Product WHERE product_name='猫罐头'") == 0:
        r = s2.post(
            BASE + "/products/new",
            data={"product_name": "猫罐头", "category": "食品", "price": "8.50", "stock_warn": "10", "status": "在售", "quantity": "2"},
            allow_redirects=False,
        )
        show(r)
        assert r.status_code == 302
    low_rows = db_rows("SELECT p.product_name, i.quantity, p.stock_warn FROM dbo.Product p JOIN dbo.Inventory i ON i.product_id=p.product_id WHERE p.product_name='猫罐头'")
    print(f"  低库存商品: {low_rows}")

    step("店长：员工列表")
    r = s2.get(BASE + "/employees")
    show(r)
    assert "王店长" in r.text and "赵店员" in r.text

    step("店长：经营报表（商品销售/库存状态/会员消费）")
    r = s2.get(BASE + "/reports")
    show(r)
    assert "商品销售" in r.text and "库存" in r.text and "会员" in r.text

    # ---------------------------------------------------------------
    step("重新以店员登录（用于异常场景验证）")
    s.post(BASE + "/login", data={"login_name": "clerk", "password": "Clerk@123"}, allow_redirects=False)

    step("库存不足：整单回滚（业务层 + 事务）")
    # P001 当前库存较少，用超量下单触发库存不足
    avail = db_scalar("SELECT quantity FROM dbo.Inventory WHERE product_id = 'P001'")
    before_orders = db_scalar("SELECT COUNT(*) FROM dbo.Orders")
    r = s.post(
        BASE + "/orders/new",
        data={"member_id": "", "pay_method": "现金", "product_id": ["P001"], "quantity": [str(avail + 9999)]},
        allow_redirects=False,
    )
    show(r)
    assert r.status_code == 400
    after_orders = db_scalar("SELECT COUNT(*) FROM dbo.Orders")
    print(f"  订单数 {before_orders} -> {after_orders}（应不变）")
    assert before_orders == after_orders

    step("停售商品下单被拒")
    r = s.post(
        BASE + "/orders/new",
        data={"member_id": "", "pay_method": "现金", "product_id": [new_pid], "quantity": ["1"]},
        allow_redirects=False,
    )
    show(r)
    assert r.status_code == 400

    step("参数错误（数量非整数）-> 400")
    r = s.post(
        BASE + "/orders/new",
        data={"member_id": "", "pay_method": "现金", "product_id": ["P001"], "quantity": ["abc"]},
        allow_redirects=False,
    )
    show(r)
    assert r.status_code == 400

    print("\n=== WALKTHROUGH COMPLETE ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
