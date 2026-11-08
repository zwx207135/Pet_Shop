"""Read-only report queries built on the existing statistical views."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pyodbc import Connection

from .errors import DAOError, ErrorCode
from .utils import (
    cursor_scope,
    dao_errors,
    ensure_int,
    ensure_text,
    rows_to_dicts,
)


class ReportDAO:
    @dao_errors
    def product_sales(
        self,
        conn: Connection,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        self._validate_range(start, end)
        if limit is not None:
            limit = ensure_int(limit, "返回条数", minimum=1)

        top = "TOP (?) " if limit is not None else ""
        top_params: list[Any] = [limit] if limit is not None else []

        if start is None and end is None:
            sql = f"""
                SELECT {top}product_id, product_name, sold_qty, sales_amount
                FROM dbo.v_product_sales
                ORDER BY sales_amount DESC, product_id;
            """
            params = top_params
        else:
            conditions: list[str] = []
            date_params: list[Any] = []
            if start is not None:
                conditions.append("o.order_time >= ?")
                date_params.append(start)
            if end is not None:
                conditions.append("o.order_time <= ?")
                date_params.append(end)
            where = f"WHERE {' AND '.join(conditions)}"
            sql = f"""
                SELECT {top}RTRIM(p.product_id) AS product_id, p.product_name,
                       ISNULL(SUM(d.quantity), 0) AS sold_qty,
                       ISNULL(SUM(d.subtotal), 0) AS sales_amount
                FROM dbo.Product p
                LEFT JOIN (
                    SELECT d.product_id, d.quantity, d.subtotal
                    FROM dbo.OrderDetail d
                    JOIN dbo.Orders o ON o.order_id = d.order_id
                    {where}
                ) d ON d.product_id = p.product_id
                GROUP BY p.product_id, p.product_name
                ORDER BY sales_amount DESC, product_id;
            """
            params = [*top_params, *date_params]

        with cursor_scope(conn) as cursor:
            cursor.execute(sql, params)
            return rows_to_dicts(cursor)

    @dao_errors
    def inventory_status(
        self,
        conn: Connection,
        *,
        low_stock_only: bool = False,
    ) -> list[dict[str, Any]]:
        where = "WHERE stock_status <> '正常'" if low_stock_only else ""
        with cursor_scope(conn) as cursor:
            cursor.execute(
                f"""
                SELECT product_id, product_name, quantity, stock_warn, stock_status
                FROM dbo.v_inventory_status
                {where}
                ORDER BY product_id;
                """
            )
            return rows_to_dicts(cursor)

    @dao_errors
    def member_consumption(
        self,
        conn: Connection,
        *,
        member_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        if limit is not None:
            limit = ensure_int(limit, "返回条数", minimum=1)

        top = "TOP (?) " if limit is not None else ""
        where = ""
        params: list[Any] = [limit] if limit is not None else []

        if member_id is not None:
            member_id = ensure_text(member_id, "会员编号", max_length=8)
            where = "WHERE member_id = ?"
            params.append(member_id)

        with cursor_scope(conn) as cursor:
            cursor.execute(
                f"""
                SELECT {top}member_id, member_name, points, order_count, total_spent
                FROM dbo.v_member_consumption
                {where}
                ORDER BY total_spent DESC, member_id;
                """,
                params,
            )
            return rows_to_dicts(cursor)

    @staticmethod
    def _validate_range(start: datetime | None, end: datetime | None) -> None:
        if start is not None and not isinstance(start, datetime):
            raise DAOError(ErrorCode.VALIDATION_ERROR, "开始时间必须是 datetime")
        if end is not None and not isinstance(end, datetime):
            raise DAOError(ErrorCode.VALIDATION_ERROR, "结束时间必须是 datetime")
        if start is not None and end is not None and start > end:
            raise DAOError(ErrorCode.VALIDATION_ERROR, "开始时间不能晚于结束时间")
