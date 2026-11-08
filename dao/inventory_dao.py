"""Inventory and inventory-log data access."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pyodbc import Connection

from .errors import DAOError, ErrorCode
from .ids import next_id
from .models import Page
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

CHANGE_TYPES = ("入库", "销售")
STOCK_STATUS_SQL = """
    CASE
        WHEN i.quantity = 0 THEN '缺货'
        WHEN i.quantity < p.stock_warn THEN '库存不足'
        ELSE '正常'
    END
"""
INVENTORY_SELECT = f"""
    SELECT i.inventory_id, i.product_id, p.product_name,
           i.quantity, p.stock_warn, {STOCK_STATUS_SQL} AS stock_status,
           i.update_time
    FROM dbo.Inventory i
    JOIN dbo.Product p ON p.product_id = i.product_id
"""


class InventoryDAO:
    @dao_errors
    def get(self, conn: Connection, product_id: str) -> dict[str, Any] | None:
        product_id = ensure_text(product_id, "商品编号", max_length=8)  # type: ignore[assignment]
        with cursor_scope(conn) as cursor:
            cursor.execute(
                f"{INVENTORY_SELECT} WHERE i.product_id = ?;",
                [product_id],
            )
            return row_to_dict(cursor)

    @dao_errors
    def list(
        self,
        conn: Connection,
        *,
        keyword: str | None = None,
        low_stock_only: bool = False,
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
                "(i.product_id LIKE ? ESCAPE '\\' OR p.product_name LIKE ? ESCAPE '\\')"
            )
            params.extend([pattern, pattern])

        if low_stock_only:
            where.append("(i.quantity = 0 OR i.quantity < p.stock_warn)")

        clause = f"WHERE {' AND '.join(where)}" if where else ""

        with cursor_scope(conn) as cursor:
            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM dbo.Inventory i
                JOIN dbo.Product p ON p.product_id = i.product_id
                {clause};
                """,
                params,
            )
            total = int(cursor.fetchone()[0])

            cursor.execute(
                f"""
                {INVENTORY_SELECT}
                {clause}
                ORDER BY i.product_id
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
                """,
                [*params, (page - 1) * page_size, page_size],
            )
            items = rows_to_dicts(cursor)

        return Page(items=items, total=total, page=page, page_size=page_size)

    @dao_errors
    def create(
        self,
        conn: Connection,
        *,
        product_id: str,
        quantity: int = 0,
        remark: str | None = None,
    ) -> dict[str, Any]:
        require_transaction(conn)
        product_id = ensure_text(product_id, "商品编号", max_length=8)  # type: ignore[assignment]
        quantity = ensure_int(quantity, "初始库存", minimum=0)
        remark = ensure_text(remark, "备注", max_length=100, required=False)

        inventory_id = next_id(conn, "inventory")
        with cursor_scope(conn) as cursor:
            cursor.execute(
                """
                INSERT INTO dbo.Inventory (inventory_id, product_id, quantity)
                VALUES (?, ?, ?);
                """,
                [inventory_id, product_id, quantity],
            )

            if quantity != 0:
                log_id = next_id(conn, "inventory_log")
                cursor.execute(
                    """
                    INSERT INTO dbo.InventoryLog
                        (log_id, product_id, change_type, change_qty, remark)
                    VALUES (?, ?, '入库', ?, ?);
                    """,
                    [log_id, product_id, quantity, remark],
                )

        created = self.get(conn, product_id)
        if created is None:
            raise DAOError(ErrorCode.INTERNAL_ERROR, "创建库存后无法读取记录")
        return created

    @dao_errors
    def adjust(
        self,
        conn: Connection,
        product_id: str,
        *,
        change_qty: int,
        change_type: Literal["入库", "销售"],
        remark: str | None = None,
    ) -> dict[str, Any]:
        require_transaction(conn)
        product_id = ensure_text(product_id, "商品编号", max_length=8)  # type: ignore[assignment]
        change_qty = ensure_int(change_qty, "变动数量")
        change_type = ensure_choice(change_type, "变动类型", CHANGE_TYPES)
        remark = ensure_text(remark, "备注", max_length=100, required=False)

        if change_qty == 0:
            raise DAOError(ErrorCode.VALIDATION_ERROR, "变动数量不能为 0")
        if change_type == "入库" and change_qty < 0:
            raise DAOError(ErrorCode.VALIDATION_ERROR, "入库数量必须为正数")
        if change_type == "销售" and change_qty > 0:
            raise DAOError(ErrorCode.VALIDATION_ERROR, "销售数量必须为负数")

        with cursor_scope(conn) as cursor:
            cursor.execute(
                """
                UPDATE dbo.Inventory
                SET quantity = quantity + ?, update_time = GETDATE()
                OUTPUT DELETED.quantity, INSERTED.quantity
                WHERE product_id = ? AND quantity + ? >= 0;
                """,
                [change_qty, product_id, change_qty],
            )
            row = cursor.fetchone()

            if row is None:
                cursor.execute(
                    "SELECT quantity FROM dbo.Inventory WHERE product_id = ?;",
                    [product_id],
                )
                existing = cursor.fetchone()
                if existing is None:
                    raise DAOError(
                        ErrorCode.NOT_FOUND,
                        "库存记录不存在",
                        context={"product_id": product_id},
                    )
                available = int(existing[0])
                raise DAOError(
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    "库存不足",
                    context={
                        "product_id": product_id,
                        "available": available,
                        "requested": -change_qty,
                    },
                )

            quantity_before = int(row[0])
            quantity_after = int(row[1])

            log_id = next_id(conn, "inventory_log")
            cursor.execute(
                """
                INSERT INTO dbo.InventoryLog
                    (log_id, product_id, change_type, change_qty, remark)
                VALUES (?, ?, ?, ?, ?);
                """,
                [log_id, product_id, change_type, change_qty, remark],
            )

        return {
            "product_id": product_id,
            "change_type": change_type,
            "change_qty": change_qty,
            "quantity_before": quantity_before,
            "quantity_after": quantity_after,
            "log_id": log_id,
            "remark": remark,
        }

    @dao_errors
    def set_warn(self, conn: Connection, product_id: str, stock_warn: int) -> dict[str, Any] | None:
        product_id = ensure_text(product_id, "商品编号", max_length=8)  # type: ignore[assignment]
        stock_warn = ensure_int(stock_warn, "预警库存", minimum=0)
        with cursor_scope(conn) as cursor:
            cursor.execute(
                "UPDATE dbo.Product SET stock_warn = ? WHERE product_id = ?;",
                [stock_warn, product_id],
            )
            if cursor.rowcount == 0:
                return None
        return self.get(conn, product_id)

    @dao_errors
    def list_logs(
        self,
        conn: Connection,
        *,
        product_id: str | None = None,
        change_type: Literal["入库", "销售"] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page:
        page, page_size = validate_page(page, page_size)

        where: list[str] = []
        params: list[Any] = []

        if product_id is not None:
            where.append("l.product_id = ?")
            params.append(ensure_text(product_id, "商品编号", max_length=8))

        if change_type is not None:
            where.append("l.change_type = ?")
            params.append(ensure_choice(change_type, "变动类型", CHANGE_TYPES))

        if start is not None:
            if not isinstance(start, datetime):
                raise DAOError(ErrorCode.VALIDATION_ERROR, "开始时间必须是 datetime")
            where.append("l.change_time >= ?")
            params.append(start)

        if end is not None:
            if not isinstance(end, datetime):
                raise DAOError(ErrorCode.VALIDATION_ERROR, "结束时间必须是 datetime")
            where.append("l.change_time <= ?")
            params.append(end)

        if start is not None and end is not None and start > end:
            raise DAOError(ErrorCode.VALIDATION_ERROR, "开始时间不能晚于结束时间")

        clause = f"WHERE {' AND '.join(where)}" if where else ""

        with cursor_scope(conn) as cursor:
            cursor.execute(
                f"SELECT COUNT(*) FROM dbo.InventoryLog l {clause};",
                params,
            )
            total = int(cursor.fetchone()[0])

            cursor.execute(
                f"""
                SELECT l.log_id, l.product_id, p.product_name,
                       l.change_type, l.change_qty, l.change_time, l.remark
                FROM dbo.InventoryLog l
                JOIN dbo.Product p ON p.product_id = l.product_id
                {clause}
                ORDER BY l.change_time DESC, l.log_id DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
                """,
                [*params, (page - 1) * page_size, page_size],
            )
            items = rows_to_dicts(cursor)

        return Page(items=items, total=total, page=page, page_size=page_size)
