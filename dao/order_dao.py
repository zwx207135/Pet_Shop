"""Order and order-detail data access."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal

from pyodbc import Connection

from .errors import DAOError, ErrorCode
from .ids import next_id
from .models import OrderItemInput, Page
from .utils import (
    cursor_scope,
    dao_errors,
    ensure_choice,
    ensure_int,
    ensure_text,
    like_pattern,
    require_transaction,
    row_to_dict,
    rows_to_dicts,
    validate_page,
)

ORDER_TYPES = ("商品", "服务")
ORDER_STATUSES = ("已完成", "未完成")
PAY_METHODS = ("现金", "微信", "支付宝")
MAX_ITEMS = 100

HEADER_SELECT = """
    SELECT order_id, member_id, member_name, employee_id, employee_name,
           order_type, order_time, total_amount, pay_method, order_status
    FROM dbo.v_order_header
"""
DETAIL_SELECT = """
    SELECT d.detail_id, RTRIM(d.order_id) AS order_id, RTRIM(d.product_id) AS product_id,
           p.product_name, d.quantity, d.unit_price, d.subtotal
    FROM dbo.OrderDetail d
    JOIN dbo.Product p ON p.product_id = d.product_id
"""


class OrderDAO:
    @dao_errors
    def create_with_details(
        self,
        conn: Connection,
        *,
        member_id: str | None,
        employee_id: str,
        pay_method: Literal["现金", "微信", "支付宝"],
        items: Sequence[OrderItemInput],
        order_type: Literal["商品", "服务"] = "商品",
        order_status: Literal["已完成", "未完成"] = "已完成",
    ) -> dict[str, Any]:
        require_transaction(conn)

        member_id = ensure_text(member_id, "会员编号", max_length=8, required=False)
        employee_id = ensure_text(employee_id, "员工编号", max_length=8)  # type: ignore[assignment]
        pay_method = ensure_choice(pay_method, "支付方式", PAY_METHODS)
        order_type = ensure_choice(order_type, "订单类型", ORDER_TYPES)
        order_status = ensure_choice(order_status, "订单状态", ORDER_STATUSES)

        merged = self._normalize_items(items)
        product_ids = sorted(merged)

        with cursor_scope(conn) as cursor:
            placeholders = ", ".join("?" for _ in product_ids)
            cursor.execute(
                f"""
                SELECT RTRIM(p.product_id) AS product_id, p.product_name,
                       p.price, p.status,
                       RTRIM(i.inventory_id) AS inventory_id, i.quantity
                FROM dbo.Product p WITH (UPDLOCK, ROWLOCK)
                LEFT JOIN dbo.Inventory i WITH (UPDLOCK, ROWLOCK)
                       ON i.product_id = p.product_id
                WHERE p.product_id IN ({placeholders})
                ORDER BY p.product_id;
                """,
                product_ids,
            )
            locked = {row[0]: row for row in cursor.fetchall()}

            products: dict[str, dict[str, Any]] = {}
            for product_id in product_ids:
                row = locked.get(product_id)
                if row is None:
                    raise DAOError(
                        ErrorCode.NOT_FOUND,
                        "商品不存在",
                        context={"product_id": product_id},
                    )
                _pid, product_name, price, status, inventory_id, available = row
                if status != "在售":
                    raise DAOError(
                        ErrorCode.BUSINESS_RULE_VIOLATION,
                        "商品已停售",
                        context={"product_id": product_id, "status": status},
                    )
                if inventory_id is None:
                    raise DAOError(
                        ErrorCode.NOT_FOUND,
                        "库存记录不存在",
                        context={"product_id": product_id},
                    )
                requested = merged[product_id]
                if int(available) < requested:
                    raise DAOError(
                        ErrorCode.BUSINESS_RULE_VIOLATION,
                        "库存不足",
                        context={
                            "product_id": product_id,
                            "available": int(available),
                            "requested": requested,
                        },
                    )
                products[product_id] = {
                    "product_name": product_name,
                    "price": Decimal(price),
                    "available": int(available),
                }

            lines = [
                {
                    "product_id": product_id,
                    "product_name": products[product_id]["product_name"],
                    "quantity": merged[product_id],
                    "unit_price": products[product_id]["price"],
                    "subtotal": (
                        products[product_id]["price"] * merged[product_id]
                    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                }
                for product_id in product_ids
            ]
            total_amount = sum(
                (line["subtotal"] for line in lines), Decimal("0.00")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            order_id = next_id(conn, "order")
            cursor.execute(
                """
                INSERT INTO dbo.Orders
                    (order_id, member_id, employee_id, order_type,
                     total_amount, pay_method, order_status)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                [
                    order_id,
                    member_id,
                    employee_id,
                    order_type,
                    total_amount,
                    pay_method,
                    order_status,
                ],
            )

            for line in lines:
                detail_id = next_id(conn, "order_detail")
                cursor.execute(
                    """
                    INSERT INTO dbo.OrderDetail
                        (detail_id, order_id, product_id, quantity, unit_price)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    [
                        detail_id,
                        order_id,
                        line["product_id"],
                        line["quantity"],
                        line["unit_price"],
                    ],
                )

                cursor.execute(
                    """
                    UPDATE dbo.Inventory
                    SET quantity = quantity - ?, update_time = GETDATE()
                    WHERE product_id = ? AND quantity >= ?;
                    """,
                    [line["quantity"], line["product_id"], line["quantity"]],
                )
                if cursor.rowcount != 1:
                    raise DAOError(
                        ErrorCode.BUSINESS_RULE_VIOLATION,
                        "库存不足",
                        context={
                            "product_id": line["product_id"],
                            "requested": line["quantity"],
                        },
                    )

                log_id = next_id(conn, "inventory_log")
                cursor.execute(
                    """
                    INSERT INTO dbo.InventoryLog
                        (log_id, product_id, change_type, change_qty, remark)
                    VALUES (?, ?, '销售', ?, ?);
                    """,
                    [
                        log_id,
                        line["product_id"],
                        -line["quantity"],
                        f"订单{order_id}",
                    ],
                )

        created = self.get(conn, order_id, include_details=True)
        if created is None:
            raise DAOError(ErrorCode.INTERNAL_ERROR, "创建订单后无法读取记录")
        return created

    @staticmethod
    def _normalize_items(items: Sequence[OrderItemInput]) -> dict[str, int]:
        if isinstance(items, (str, bytes)) or not isinstance(items, Sequence):
            raise DAOError(ErrorCode.VALIDATION_ERROR, "订单明细必须是列表")
        if not items:
            raise DAOError(ErrorCode.VALIDATION_ERROR, "订单明细不能为空")
        if len(items) > MAX_ITEMS:
            raise DAOError(
                ErrorCode.VALIDATION_ERROR,
                f"单笔订单最多 {MAX_ITEMS} 行明细",
                context={"max_items": MAX_ITEMS},
            )

        merged: dict[str, int] = {}
        for item in items:
            if not isinstance(item, OrderItemInput):
                raise DAOError(
                    ErrorCode.VALIDATION_ERROR,
                    "订单明细项必须是 OrderItemInput",
                )
            product_id = ensure_text(item.product_id, "商品编号", max_length=8)
            quantity = ensure_int(item.quantity, "购买数量", minimum=1)
            merged[product_id] = merged.get(product_id, 0) + quantity  # type: ignore[index]
        return merged

    @dao_errors
    def get(
        self,
        conn: Connection,
        order_id: str,
        *,
        include_details: bool = True,
    ) -> dict[str, Any] | None:
        order_id = ensure_text(order_id, "订单编号", max_length=12)  # type: ignore[assignment]
        with cursor_scope(conn) as cursor:
            cursor.execute(f"{HEADER_SELECT} WHERE order_id = ?;", [order_id])
            header = row_to_dict(cursor)
        if header is None:
            return None
        if include_details:
            header["details"] = self.list_details(conn, order_id)
        return header

    @dao_errors
    def list(
        self,
        conn: Connection,
        *,
        keyword: str | None = None,
        member_id: str | None = None,
        employee_id: str | None = None,
        order_status: Literal["已完成", "未完成"] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page:
        page, page_size = validate_page(page, page_size)

        where: list[str] = []
        params: list[Any] = []

        keyword = ensure_text(keyword, "关键字", max_length=50, required=False)
        if keyword:
            pattern = like_pattern(keyword)
            where.append(
                "(order_id LIKE ? ESCAPE '\\' OR member_name LIKE ? ESCAPE '\\' "
                "OR employee_name LIKE ? ESCAPE '\\')"
            )
            params.extend([pattern, pattern, pattern])

        if member_id is not None:
            where.append("member_id = ?")
            params.append(ensure_text(member_id, "会员编号", max_length=8))

        if employee_id is not None:
            where.append("employee_id = ?")
            params.append(ensure_text(employee_id, "员工编号", max_length=8))

        if order_status is not None:
            where.append("order_status = ?")
            params.append(ensure_choice(order_status, "订单状态", ORDER_STATUSES))

        if start is not None:
            if not isinstance(start, datetime):
                raise DAOError(ErrorCode.VALIDATION_ERROR, "开始时间必须是 datetime")
            where.append("order_time >= ?")
            params.append(start)

        if end is not None:
            if not isinstance(end, datetime):
                raise DAOError(ErrorCode.VALIDATION_ERROR, "结束时间必须是 datetime")
            where.append("order_time <= ?")
            params.append(end)

        if start is not None and end is not None and start > end:
            raise DAOError(ErrorCode.VALIDATION_ERROR, "开始时间不能晚于结束时间")

        clause = f"WHERE {' AND '.join(where)}" if where else ""

        with cursor_scope(conn) as cursor:
            cursor.execute(
                f"SELECT COUNT(*) FROM dbo.v_order_header {clause};",
                params,
            )
            total = int(cursor.fetchone()[0])

            cursor.execute(
                f"""
                {HEADER_SELECT}
                {clause}
                ORDER BY order_time DESC, order_id DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
                """,
                [*params, (page - 1) * page_size, page_size],
            )
            items = rows_to_dicts(cursor)

        return Page(items=items, total=total, page=page, page_size=page_size)

    @dao_errors
    def update_status(
        self,
        conn: Connection,
        order_id: str,
        status: Literal["已完成", "未完成"],
    ) -> dict[str, Any] | None:
        order_id = ensure_text(order_id, "订单编号", max_length=12)  # type: ignore[assignment]
        status = ensure_choice(status, "订单状态", ORDER_STATUSES)
        with cursor_scope(conn) as cursor:
            cursor.execute(
                "UPDATE dbo.Orders SET order_status = ? WHERE order_id = ?;",
                [status, order_id],
            )
            if cursor.rowcount == 0:
                return None
        return self.get(conn, order_id, include_details=False)

    @dao_errors
    def list_details(self, conn: Connection, order_id: str) -> list[dict[str, Any]]:
        order_id = ensure_text(order_id, "订单编号", max_length=12)  # type: ignore[assignment]
        with cursor_scope(conn) as cursor:
            cursor.execute(
                f"{DETAIL_SELECT} WHERE d.order_id = ? ORDER BY d.detail_id;",
                [order_id],
            )
            return rows_to_dicts(cursor)
