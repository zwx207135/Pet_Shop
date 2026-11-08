"""库存与库存流水页面（成员B）。补货入库为店长专属。"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from dao import DAOError

from app.routes.common import flash_error
from app.security import login_required, roles_required
from app.services import inventory_service

bp = Blueprint("inventory", __name__)

CHANGE_TYPES = ("入库", "销售")


@bp.route("/inventory")
@login_required
def list():
    q = request.args.get("q") or None
    low_stock_only = request.args.get("low_stock_only") == "1"
    page = request.args.get("page", 1, type=int)
    result = inventory_service.list_inventory(
        keyword=q, low_stock_only=low_stock_only, page=page
    )
    return render_template(
        "inventory.html", page=result, q=q, low_stock_only=low_stock_only
    )


@bp.route("/inventory/logs")
@login_required
def logs():
    product_id = request.args.get("product_id") or None
    change_type = request.args.get("change_type") or None
    page = request.args.get("page", 1, type=int)
    result = inventory_service.list_logs(
        product_id=product_id, change_type=change_type, page=page
    )
    return render_template(
        "inventory_logs.html",
        page=result,
        product_id=product_id,
        change_type=change_type,
        change_types=CHANGE_TYPES,
    )


@bp.route("/inventory/<product_id>/adjust", methods=["GET", "POST"])
@roles_required("店长")
def adjust(product_id):
    inventory = inventory_service.get_inventory(product_id)
    if inventory is None:
        flash("库存记录不存在", "danger")
        return redirect(url_for("inventory.list"))

    if request.method == "POST":
        change_qty = inventory_service.parse_change_qty(request.form.get("change_qty"))
        remark = request.form.get("remark") or None
        try:
            inventory_service.adjust_inventory(
                product_id,
                change_qty=change_qty,
                change_type="入库",
                remark=remark,
            )
        except DAOError as exc:
            flash_error(exc)
            return render_template(
                "inventory_adjust.html", inventory=inventory, form=request.form
            ), 400
        flash("入库成功", "success")
        return redirect(url_for("inventory.list"))
    return render_template("inventory_adjust.html", inventory=inventory, form={})
