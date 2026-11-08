"""首页 / 工作台。"""

from __future__ import annotations

from flask import Blueprint, render_template
from dao import DAOError

from app.security import login_required
from app.services import report_service

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    low_stock: list[dict] = []
    try:
        low_stock = report_service.inventory_status(low_stock_only=True)
    except DAOError:
        # 数据库不可用时不阻断首页展示，只隐藏预警信息
        pass
    return render_template("index.html", low_stock=low_stock)
