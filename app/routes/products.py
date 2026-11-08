"""商品页面（成员B）。新增/编辑/停售为店长专属。"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from dao import DAOError

from app.routes.common import flash_error
from app.security import login_required, roles_required
from app.services import product_service

bp = Blueprint("products", __name__)

STATUSES = ("在售", "停售")


@bp.route("/products")
@login_required
def list():
    q = request.args.get("q") or None
    category = request.args.get("category") or None
    status = request.args.get("status") or None
    page = request.args.get("page", 1, type=int)
    result = product_service.list_products(
        keyword=q, category=category, status=status, page=page
    )
    categories = product_service.list_categories()
    return render_template(
        "products.html",
        page=result,
        categories=categories,
        q=q,
        category=category,
        status=status,
        statuses=STATUSES,
    )


@bp.route("/products/new", methods=["GET", "POST"])
@roles_required("店长")
def create():
    categories = product_service.list_categories()
    if request.method == "POST":
        try:
            product_service.create_product(request.form)
        except DAOError as exc:
            flash_error(exc)
            return render_template(
                "product_form.html",
                product=None,
                categories=categories,
                form=request.form,
                statuses=STATUSES,
            ), 400
        flash("商品已创建", "success")
        return redirect(url_for("products.list"))
    return render_template(
        "product_form.html",
        product=None,
        categories=categories,
        form={},
        statuses=STATUSES,
    )


@bp.route("/products/<product_id>/edit", methods=["GET", "POST"])
@roles_required("店长")
def edit(product_id):
    categories = product_service.list_categories()
    product = product_service.get_product(product_id)
    if product is None:
        flash("商品不存在", "danger")
        return redirect(url_for("products.list"))

    if request.method == "POST":
        try:
            product_service.update_product(product_id, request.form)
        except DAOError as exc:
            flash_error(exc)
            return render_template(
                "product_form.html",
                product=product,
                categories=categories,
                form=request.form,
                statuses=STATUSES,
            ), 400
        flash("商品已更新", "success")
        return redirect(url_for("products.list"))
    return render_template(
        "product_form.html",
        product=product,
        categories=categories,
        form=product,
        statuses=STATUSES,
    )


@bp.post("/products/<product_id>/status")
@roles_required("店长")
def set_status(product_id):
    status = request.form.get("status", "在售")
    try:
        product_service.set_status(product_id, status)
    except DAOError as exc:
        flash_error(exc)
    else:
        flash(f"商品已{status}", "success")
    return redirect(url_for("products.list"))
