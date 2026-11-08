"""Product data access."""

from __future__ import annotations

from typing import Any, Literal

from pyodbc import Connection

from .errors import DAOError, ErrorCode
from .ids import next_id
from .models import Page
from .utils import (
    cursor_scope,
    dao_errors,
    ensure_choice,
    ensure_decimal,
    ensure_int,
    ensure_text,
    like_pattern,
    row_to_dict,
    rows_to_dicts,
    validate_page,
)

STATUSES = ("在售", "停售")
PRODUCT_COLUMNS = "product_id, product_name, category, price, stock_warn, status"
UPDATABLE = ("product_name", "category", "price", "stock_warn", "status")


class ProductDAO:
    @dao_errors
    def list(
        self,
        conn: Connection,
        *,
        keyword: str | None = None,
        category: str | None = None,
        status: Literal["在售", "停售"] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page:
        page, page_size = validate_page(page, page_size)

        where: list[str] = []
        params: list[Any] = []

        keyword = ensure_text(keyword, "关键字", max_length=50, required=False)
        if keyword:
            pattern = like_pattern(keyword)
            where.append("(product_id LIKE ? ESCAPE '\\' OR product_name LIKE ? ESCAPE '\\')")
            params.extend([pattern, pattern])

        category = ensure_text(category, "类别", max_length=20, required=False)
        if category:
            where.append("category = ?")
            params.append(category)

        if status is not None:
            where.append("status = ?")
            params.append(ensure_choice(status, "商品状态", STATUSES))

        clause = f"WHERE {' AND '.join(where)}" if where else ""

        with cursor_scope(conn) as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM dbo.Product {clause};", params)
            total = int(cursor.fetchone()[0])

            cursor.execute(
                f"""
                SELECT {PRODUCT_COLUMNS}
                FROM dbo.Product
                {clause}
                ORDER BY product_id
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
                """,
                [*params, (page - 1) * page_size, page_size],
            )
            items = rows_to_dicts(cursor)

        return Page(items=items, total=total, page=page, page_size=page_size)

    @dao_errors
    def get(self, conn: Connection, product_id: str) -> dict[str, Any] | None:
        product_id = ensure_text(product_id, "商品编号", max_length=8)  # type: ignore[assignment]
        with cursor_scope(conn) as cursor:
            cursor.execute(
                f"SELECT {PRODUCT_COLUMNS} FROM dbo.Product WHERE product_id = ?;",
                [product_id],
            )
            return row_to_dict(cursor)

    @dao_errors
    def create(
        self,
        conn: Connection,
        *,
        product_name: str,
        category: str | None,
        price: Any,
        stock_warn: int = 10,
        status: Literal["在售", "停售"] = "在售",
    ) -> dict[str, Any]:
        product_name = ensure_text(product_name, "商品名称", max_length=50)  # type: ignore[assignment]
        category = ensure_text(category, "类别", max_length=20, required=False)
        price = ensure_decimal(price, "单价")
        stock_warn = ensure_int(stock_warn, "预警库存", minimum=0)
        status = ensure_choice(status, "商品状态", STATUSES)

        product_id = next_id(conn, "product")
        with cursor_scope(conn) as cursor:
            cursor.execute(
                """
                INSERT INTO dbo.Product
                    (product_id, product_name, category, price, stock_warn, status)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                [product_id, product_name, category, price, stock_warn, status],
            )
        created = self.get(conn, product_id)
        if created is None:
            raise DAOError(ErrorCode.INTERNAL_ERROR, "创建商品后无法读取记录")
        return created

    @dao_errors
    def update(
        self,
        conn: Connection,
        product_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any] | None:
        product_id = ensure_text(product_id, "商品编号", max_length=8)  # type: ignore[assignment]
        if not isinstance(changes, dict):
            raise DAOError(ErrorCode.VALIDATION_ERROR, "changes 必须是字典")

        unknown = set(changes) - set(UPDATABLE)
        if unknown:
            raise DAOError(
                ErrorCode.VALIDATION_ERROR,
                f"不允许修改字段：{', '.join(sorted(unknown))}",
                context={"fields": sorted(unknown)},
            )

        assignments: list[str] = []
        params: list[Any] = []

        if "product_name" in changes:
            assignments.append("product_name = ?")
            params.append(
                ensure_text(changes["product_name"], "商品名称", max_length=50)
            )
        if "category" in changes:
            assignments.append("category = ?")
            params.append(
                ensure_text(changes["category"], "类别", max_length=20, required=False)
            )
        if "price" in changes:
            assignments.append("price = ?")
            params.append(ensure_decimal(changes["price"], "单价"))
        if "stock_warn" in changes:
            assignments.append("stock_warn = ?")
            params.append(ensure_int(changes["stock_warn"], "预警库存", minimum=0))
        if "status" in changes:
            assignments.append("status = ?")
            params.append(ensure_choice(changes["status"], "商品状态", STATUSES))

        if not assignments:
            return self.get(conn, product_id)

        params.append(product_id)
        with cursor_scope(conn) as cursor:
            cursor.execute(
                f"UPDATE dbo.Product SET {', '.join(assignments)} WHERE product_id = ?;",
                params,
            )
            if cursor.rowcount == 0:
                return None
        return self.get(conn, product_id)

    @dao_errors
    def set_status(
        self,
        conn: Connection,
        product_id: str,
        status: Literal["在售", "停售"],
    ) -> dict[str, Any] | None:
        return self.update(conn, product_id, {"status": status})

    @dao_errors
    def delete(self, conn: Connection, product_id: str) -> bool:
        product_id = ensure_text(product_id, "商品编号", max_length=8)  # type: ignore[assignment]
        with cursor_scope(conn) as cursor:
            cursor.execute("DELETE FROM dbo.Product WHERE product_id = ?;", [product_id])
            return cursor.rowcount > 0

    @dao_errors
    def list_categories(self, conn: Connection) -> list[str]:
        with cursor_scope(conn) as cursor:
            cursor.execute(
                """
                SELECT DISTINCT category
                FROM dbo.Product
                WHERE category IS NOT NULL AND category <> ''
                ORDER BY category;
                """
            )
            return [row[0].rstrip() for row in cursor.fetchall()]
