"""统计报表业务（成员B）。店长专用：经营数据查看。"""

from __future__ import annotations

from datetime import datetime

from dao import ReportDAO

from app.extensions import get_db


def product_sales(*, start: datetime | None = None, end: datetime | None = None, limit: int | None = None):
    with get_db().read("manager") as conn:
        return ReportDAO().product_sales(conn, start=start, end=end, limit=limit)


def inventory_status(*, low_stock_only: bool = False):
    with get_db().read("manager") as conn:
        return ReportDAO().inventory_status(conn, low_stock_only=low_stock_only)


def member_consumption(*, member_id: str | None = None, limit: int | None = None):
    with get_db().read("manager") as conn:
        return ReportDAO().member_consumption(conn, member_id=member_id, limit=limit)
