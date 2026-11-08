"""统计报表页面（成员B）。店长专属：经营数据查看。"""

from __future__ import annotations

from flask import Blueprint, render_template

from app.security import roles_required
from app.services import report_service

bp = Blueprint("reports", __name__)


@bp.route("/reports")
@roles_required("店长")
def index():
    sales = report_service.product_sales(limit=20)
    stock = report_service.inventory_status()
    consumption = report_service.member_consumption(limit=20)
    return render_template(
        "reports.html", sales=sales, stock=stock, consumption=consumption
    )
