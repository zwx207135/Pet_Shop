"""商品业务（成员B）。

业务规则：商品的新增/修改/停售属于店长职责，路由层用 ``roles_required("店长")``
拦截；service 本身只组织事务并调用 DAO。
"""

from __future__ import annotations

from dao import DAOError, ErrorCode, InventoryDAO, ProductDAO

from app.extensions import get_db
from app.security import db_role
from app.services.validation import parse_int


def list_products(*, keyword=None, category=None, status=None, page=1, page_size=20):
    with get_db().read(db_role()) as conn:
        return ProductDAO().list(
            conn,
            keyword=keyword,
            category=category,
            status=status,
            page=page,
            page_size=page_size,
        )


def list_categories() -> list[str]:
    with get_db().read(db_role()) as conn:
        return ProductDAO().list_categories(conn)


def get_product(product_id: str):
    with get_db().read(db_role()) as conn:
        return ProductDAO().get(conn, product_id)


def create_product(form: dict) -> dict:
    """新增商品，并在同一事务内创建库存行（DAO 契约 5.1）。"""
    product_name = form.get("product_name", "")
    category = form.get("category") or None
    price = form.get("price", "0")
    stock_warn = parse_int(form.get("stock_warn"), "预警库存", default=10, minimum=0)
    status = form.get("status", "在售")
    quantity = parse_int(form.get("quantity"), "初始库存", default=0, minimum=0)

    with get_db().transaction("manager") as conn:
        product = ProductDAO().create(
            conn,
            product_name=product_name,
            category=category,
            price=price,
            stock_warn=stock_warn,
            status=status,
        )
        InventoryDAO().create(
            conn,
            product_id=product["product_id"],
            quantity=quantity,
            remark="新商品初始入库",
        )
    return product


def update_product(product_id: str, form: dict) -> dict:
    changes = {
        "product_name": form.get("product_name", ""),
        "category": form.get("category") or None,
        "price": form.get("price", "0"),
        "stock_warn": parse_int(form.get("stock_warn"), "预警库存", default=10, minimum=0),
        "status": form.get("status", "在售"),
    }
    with get_db().transaction("manager") as conn:
        updated = ProductDAO().update(conn, product_id, changes)
    if updated is None:
        raise DAOError(ErrorCode.NOT_FOUND, "商品不存在")
    return updated


def set_status(product_id: str, status: str) -> dict:
    with get_db().transaction("manager") as conn:
        updated = ProductDAO().set_status(conn, product_id, status)
    if updated is None:
        raise DAOError(ErrorCode.NOT_FOUND, "商品不存在")
    return updated
