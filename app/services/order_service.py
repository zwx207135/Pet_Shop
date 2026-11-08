"""订单业务（成员B）。

``create_with_details`` 必须在事务内调用（DAO 契约 5.3），事务边界由本层
``db.transaction(...)`` 承担；库存校验、价格取值、扣减、流水都由 DAO 原子完成。
"""

from __future__ import annotations

from flask import session

from dao import OrderDAO, OrderItemInput

from app.extensions import get_db
from app.security import db_role


def list_orders(*, keyword=None, order_status=None, page=1, page_size=20):
    with get_db().read(db_role()) as conn:
        return OrderDAO().list(
            conn,
            keyword=keyword,
            order_status=order_status,
            page=page,
            page_size=page_size,
        )


def get_order(order_id: str, *, include_details: bool = True):
    with get_db().read(db_role()) as conn:
        return OrderDAO().get(conn, order_id, include_details=include_details)


def create_order(*, member_id: str | None, pay_method: str, items: list[tuple[str, int]]) -> dict:
    """创建订单；``items`` 为 [(product_id, quantity), ...]。

    价格不接受前端传入，由 DAO 读取 ``Product.price``；重复商品由 DAO 合并。
    """
    order_items = [OrderItemInput(product_id=pid, quantity=qty) for pid, qty in items]
    employee_id = session["employee_id"]
    with get_db().transaction(db_role()) as conn:
        return OrderDAO().create_with_details(
            conn,
            member_id=member_id or None,
            employee_id=employee_id,
            pay_method=pay_method,
            items=order_items,
        )


def update_status(order_id: str, status: str) -> dict:
    from dao import DAOError, ErrorCode

    with get_db().transaction(db_role()) as conn:
        updated = OrderDAO().update_status(conn, order_id, status)
    if updated is None:
        raise DAOError(ErrorCode.NOT_FOUND, "订单不存在")
    return updated
