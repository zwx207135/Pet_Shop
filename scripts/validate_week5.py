"""Re-run the week-5 ER/data validation queries against a PetCare database.

Usage:
    py scripts/validate_week5.py
    py scripts/validate_week5.py --database PetCareDB --output result/week5_validation.txt
"""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

import pyodbc

SEP = "-" * 60


def fmt(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return str(value)


def table(cur: pyodbc.Cursor, title: str, header: list[str], sql: str) -> list[str]:
    cur.execute(sql)
    lines = [f"===== {title} =====", " | ".join(header), SEP]
    for row in cur.fetchall():
        lines.append(" | ".join(fmt(value) for value in row))
    lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="PetCareDB")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--server", default="localhost")
    parser.add_argument("--driver", default="ODBC Driver 18 for SQL Server")
    args = parser.parse_args()

    conn_str = (
        f"DRIVER={{{args.driver}}};SERVER={args.server};DATABASE={args.database};"
        "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str, autocommit=True)
    cur = conn.cursor()

    lines = [
        "PetCare v1.0 第5周 ER 模型数据验证",
        f"数据库：{args.database}",
        "",
    ]

    lines += table(
        cur,
        "实体行数",
        ["表名", "行数"],
        """
        SELECT 'Product', COUNT(*) FROM dbo.Product
        UNION ALL SELECT 'Inventory', COUNT(*) FROM dbo.Inventory
        UNION ALL SELECT 'InventoryLog', COUNT(*) FROM dbo.InventoryLog
        UNION ALL SELECT 'Member', COUNT(*) FROM dbo.Member
        UNION ALL SELECT 'Employee', COUNT(*) FROM dbo.Employee
        UNION ALL SELECT 'Orders', COUNT(*) FROM dbo.Orders
        UNION ALL SELECT 'OrderDetail', COUNT(*) FROM dbo.OrderDetail
        UNION ALL SELECT 'PetService', COUNT(*) FROM dbo.PetService
        UNION ALL SELECT 'ServiceAppointment', COUNT(*) FROM dbo.ServiceAppointment;
        """,
    )

    lines += table(
        cur,
        "基数检查（全部应为 0 或符合说明）",
        ["检查项", "数量"],
        """
        SELECT N'有库存但无商品（应为0）', COUNT(*)
        FROM dbo.Inventory i
        LEFT JOIN dbo.Product p ON i.product_id = p.product_id
        WHERE p.product_id IS NULL
        UNION ALL
        SELECT N'有订单但无明细（业务规则要求0）', COUNT(*)
        FROM dbo.Orders o
        WHERE NOT EXISTS (SELECT 1 FROM dbo.OrderDetail d WHERE d.order_id = o.order_id)
        UNION ALL
        SELECT N'有明细但无订单（应为0）', COUNT(*)
        FROM dbo.OrderDetail d
        LEFT JOIN dbo.Orders o ON d.order_id = o.order_id
        WHERE o.order_id IS NULL
        UNION ALL
        SELECT N'同一订单重复商品行（DAO应合并为0）', COUNT(*)
        FROM (
            SELECT order_id, product_id
            FROM dbo.OrderDetail
            GROUP BY order_id, product_id
            HAVING COUNT(*) > 1
        ) dup
        UNION ALL
        SELECT N'商品但无库存（允许，0..1）', COUNT(*)
        FROM dbo.Product p
        LEFT JOIN dbo.Inventory i ON p.product_id = i.product_id
        WHERE i.inventory_id IS NULL;
        """,
    )

    lines += table(
        cur,
        "多商品订单 O2025010101 明细",
        ["detail_id", "product_id", "product_name", "quantity", "unit_price", "subtotal"],
        """
        SELECT d.detail_id, d.product_id, p.product_name,
               d.quantity, d.unit_price, d.subtotal
        FROM dbo.OrderDetail d
        JOIN dbo.Product p ON d.product_id = p.product_id
        WHERE d.order_id = 'O2025010101'
        ORDER BY d.detail_id;
        """,
    )

    cur.execute(
        """
        SELECT o.order_id, o.total_amount, ISNULL(SUM(d.subtotal), 0) AS detail_total
        FROM dbo.Orders o
        LEFT JOIN dbo.OrderDetail d ON o.order_id = d.order_id
        GROUP BY o.order_id, o.total_amount
        ORDER BY o.order_id;
        """
    )
    order_lines = [
        "===== 订单总额与明细合计一致性 =====",
        "order_id | 订单总额 | 明细合计 | 结论",
        SEP,
    ]
    for order_id, total, detail_total in cur.fetchall():
        ok = "一致" if total == detail_total else "不一致"
        order_lines.append(f"{fmt(order_id)} | {fmt(total)} | {fmt(detail_total)} | {ok}")
    order_lines.append("")
    lines += order_lines

    lines += table(
        cur,
        "会员订单与散客订单",
        ["类型", "订单数", "金额"],
        """
        SELECT order_type, order_count, amount
        FROM (
            SELECT CASE WHEN member_id IS NULL THEN N'散客' ELSE N'会员' END AS order_type,
                   COUNT(*) AS order_count, SUM(total_amount) AS amount
            FROM dbo.Orders
            GROUP BY CASE WHEN member_id IS NULL THEN N'散客' ELSE N'会员' END
        ) t
        ORDER BY CASE WHEN order_type = N'散客' THEN 1 ELSE 0 END;
        """,
    )

    lines += table(
        cur,
        "每个订单的明细数（最小应为1）",
        ["order_id", "明细数"],
        """
        SELECT order_id, COUNT(*) FROM dbo.OrderDetail
        GROUP BY order_id ORDER BY order_id;
        """,
    )

    lines += table(
        cur,
        "每个商品的库存行数（应为0或1）",
        ["product_id", "product_name", "库存行数"],
        """
        SELECT p.product_id, p.product_name, COUNT(i.inventory_id)
        FROM dbo.Product p
        LEFT JOIN dbo.Inventory i ON p.product_id = i.product_id
        GROUP BY p.product_id, p.product_name
        ORDER BY p.product_id;
        """,
    )

    lines += table(
        cur,
        "库存状态查询",
        ["product_id", "product_name", "quantity", "stock_warn", "stock_status"],
        """
        SELECT product_id, product_name, quantity, stock_warn, stock_status
        FROM dbo.v_inventory_status
        ORDER BY product_id;
        """,
    )

    lines += table(
        cur,
        "会员下单数（含0）",
        ["member_id", "member_name", "订单数"],
        """
        SELECT m.member_id, m.member_name, COUNT(o.order_id)
        FROM dbo.Member m
        LEFT JOIN dbo.Orders o ON m.member_id = o.member_id
        GROUP BY m.member_id, m.member_name
        ORDER BY m.member_id;
        """,
    )

    lines += table(
        cur,
        "员工经办订单数（含0）",
        ["employee_id", "employee_name", "订单数"],
        """
        SELECT e.employee_id, e.employee_name, COUNT(o.order_id)
        FROM dbo.Employee e
        LEFT JOIN dbo.Orders o ON e.employee_id = o.employee_id
        GROUP BY e.employee_id, e.employee_name
        ORDER BY e.employee_id;
        """,
    )

    lines += table(
        cur,
        "服务项目预约数（含0）",
        ["service_id", "service_name", "预约数"],
        """
        SELECT s.service_id, s.service_name, COUNT(a.appointment_id)
        FROM dbo.PetService s
        LEFT JOIN dbo.ServiceAppointment a ON s.service_id = a.service_id
        GROUP BY s.service_id, s.service_name
        ORDER BY s.service_id;
        """,
    )

    cur.close()
    conn.close()

    text = "\n".join(lines)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"written {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
