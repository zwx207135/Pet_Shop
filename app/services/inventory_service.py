"""库存与库存流水业务（成员B）。"""

from __future__ import annotations

from datetime import datetime

from dao import InventoryDAO

from app.extensions import get_db
from app.security import db_role
from app.services.validation import parse_int


def list_inventory(*, keyword=None, low_stock_only=False, page=1, page_size=20):
    with get_db().read(db_role()) as conn:
        return InventoryDAO().list(
            conn,
            keyword=keyword,
            low_stock_only=low_stock_only,
            page=page,
            page_size=page_size,
        )


def get_inventory(product_id: str):
    with get_db().read(db_role()) as conn:
        return InventoryDAO().get(conn, product_id)


def adjust_inventory(product_id: str, *, change_qty: int, change_type: str, remark: str | None = None) -> dict:
    """调整库存（补货入库），原子执行并写流水。"""
    with get_db().transaction(db_role()) as conn:
        return InventoryDAO().adjust(
            conn,
            product_id,
            change_qty=change_qty,
            change_type=change_type,
            remark=remark or None,
        )


def set_warn(product_id: str, stock_warn: int) -> dict:
    with get_db().transaction(db_role()) as conn:
        updated = InventoryDAO().set_warn(conn, product_id, stock_warn)
    if updated is None:
        from dao import DAOError, ErrorCode

        raise DAOError(ErrorCode.NOT_FOUND, "商品不存在")
    return updated


def list_logs(
    *,
    product_id=None,
    change_type=None,
    start: datetime | None = None,
    end: datetime | None = None,
    page=1,
    page_size=20,
):
    with get_db().read(db_role()) as conn:
        return InventoryDAO().list_logs(
            conn,
            product_id=product_id,
            change_type=change_type,
            start=start,
            end=end,
            page=page,
            page_size=page_size,
        )


def parse_change_qty(raw) -> int:
    """入库数量必须为正整数。"""
    return parse_int(raw, "入库数量", minimum=1)
