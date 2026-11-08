"""订单页面（成员B）。"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from dao import DAOError, ErrorCode

from app.routes.common import flash_error
from app.security import login_required
from app.services import member_service, order_service, product_service
from app.services.validation import parse_int

bp = Blueprint("orders", __name__)

ORDER_STATUSES = ("已完成", "未完成")
PAY_METHODS = ("现金", "微信", "支付宝")


@bp.route("/orders")
@login_required
def list():
    q = request.args.get("q") or None
    order_status = request.args.get("order_status") or None
    page = request.args.get("page", 1, type=int)
    result = order_service.list_orders(keyword=q, order_status=order_status, page=page)
    return render_template(
        "orders.html",
        page=result,
        q=q,
        order_status=order_status,
        statuses=ORDER_STATUSES,
    )


@bp.route("/orders/new", methods=["GET", "POST"])
@login_required
def create():
    members = member_service.list_members_for_select()
    products = product_service.list_products(status="在售", page=1, page_size=100).items

    if request.method == "POST":
        member_id = request.form.get("member_id") or None
        pay_method = request.form.get("pay_method", "现金")
        items = _parse_items(request.form.getlist("product_id"), request.form.getlist("quantity"))
        try:
            order = order_service.create_order(
                member_id=member_id, pay_method=pay_method, items=items
            )
        except DAOError as exc:
            flash_error(exc)
            return render_template(
                "order_create.html",
                members=members,
                products=products,
                form=request.form,
                pay_methods=PAY_METHODS,
            ), 400
        flash("订单已创建", "success")
        return redirect(url_for("orders.detail", order_id=order["order_id"]))

    return render_template(
        "order_create.html",
        members=members,
        products=products,
        form={},
        pay_methods=PAY_METHODS,
    )


@bp.route("/orders/<order_id>")
@login_required
def detail(order_id):
    order = order_service.get_order(order_id, include_details=True)
    if order is None:
        flash("订单不存在", "danger")
        return redirect(url_for("orders.list"))
    return render_template("order_detail.html", order=order)


@bp.post("/orders/<order_id>/status")
@login_required
def update_status(order_id):
    status = request.form.get("order_status", "已完成")
    try:
        order_service.update_status(order_id, status)
    except DAOError as exc:
        flash_error(exc)
    else:
        flash("订单状态已更新", "success")
    return redirect(url_for("orders.detail", order_id=order_id))


def _parse_items(product_ids, quantities) -> list[tuple[str, int]]:
    items: list[tuple[str, int]] = []
    for pid, qty_raw in zip(product_ids, quantities):
        pid = (pid or "").strip()
        if not pid:
            continue
        qty = parse_int(qty_raw, "购买数量", minimum=1)
        items.append((pid, qty))
    if not items:
        raise DAOError(ErrorCode.VALIDATION_ERROR, "请至少选择一件商品")
    return items
