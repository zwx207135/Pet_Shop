"""Capture key query results before/after the v0.1 -> v1.0 migration.

Usage:
    py scripts/capture_results.py --database PetCareDB_v01 --output result/week6_baseline.txt
    py scripts/capture_results.py --database PetCareDB     --output result/week6_after.txt
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pyodbc

QUERIES: list[tuple[str, str]] = [
    (
        "row counts",
        """
        SELECT 'Product' AS object_name, COUNT(*) AS row_count FROM dbo.Product
        UNION ALL SELECT 'Inventory', COUNT(*) FROM dbo.Inventory
        UNION ALL SELECT 'InventoryLog', COUNT(*) FROM dbo.InventoryLog
        UNION ALL SELECT 'Member', COUNT(*) FROM dbo.Member
        UNION ALL SELECT 'Employee', COUNT(*) FROM dbo.Employee
        UNION ALL SELECT 'Orders', COUNT(*) FROM dbo.Orders
        UNION ALL SELECT 'OrderDetail', COUNT(*) FROM dbo.OrderDetail
        UNION ALL SELECT 'PetService', COUNT(*) FROM dbo.PetService
        UNION ALL SELECT 'ServiceAppointment', COUNT(*) FROM dbo.ServiceAppointment;
        """,
    ),
    (
        "v_order_detail",
        """
        SELECT order_id, member_name, employee_name, product_name,
               quantity, unit_price, subtotal
        FROM dbo.v_order_detail
        ORDER BY order_id, product_name;
        """,
    ),
    (
        "v_product_sales",
        """
        SELECT product_id, product_name, sold_qty, sales_amount
        FROM dbo.v_product_sales
        ORDER BY product_id;
        """,
    ),
    (
        "v_inventory_status",
        """
        SELECT product_id, product_name, quantity, stock_warn, stock_status
        FROM dbo.v_inventory_status
        ORDER BY product_id;
        """,
    ),
    (
        "v_member_consumption",
        """
        SELECT member_id, member_name, points, order_count, total_spent
        FROM dbo.v_member_consumption
        ORDER BY member_id;
        """,
    ),
    (
        "order total vs detail sum",
        """
        SELECT o.order_id, o.total_amount,
               ISNULL(SUM(d.subtotal), 0) AS detail_total,
               COUNT(d.detail_id) AS detail_lines
        FROM dbo.Orders o
        LEFT JOIN dbo.OrderDetail d ON o.order_id = d.order_id
        GROUP BY o.order_id, o.total_amount
        ORDER BY o.order_id;
        """,
    ),
    (
        "Employee columns",
        """
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'Employee'
        ORDER BY ORDINAL_POSITION;
        """,
    ),
]


def fmt(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    return str(value).rstrip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--server", default="localhost")
    parser.add_argument("--driver", default="ODBC Driver 18 for SQL Server")
    args = parser.parse_args()

    conn_str = (
        f"DRIVER={{{args.driver}}};SERVER={args.server};DATABASE={args.database};"
        "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    lines: list[str] = [f"# Database: {args.database}", ""]
    for title, sql in QUERIES:
        lines.append(f"## {title}")
        cursor.execute(sql)
        columns = [description[0] for description in cursor.description]
        lines.append(" | ".join(columns))
        lines.append(" | ".join("---" for _ in columns))
        for row in cursor.fetchall():
            lines.append(" | ".join(fmt(value) for value in row))
        lines.append("")

    cursor.close()
    conn.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"written {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
