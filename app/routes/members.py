"""会员页面（成员B）。"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from dao import DAOError

from app.routes.common import flash_error
from app.security import login_required
from app.services import member_service
from app.services.validation import parse_int

bp = Blueprint("members", __name__)


@bp.route("/members")
@login_required
def list():
    q = request.args.get("q") or None
    page = request.args.get("page", 1, type=int)
    result = member_service.search_members(keyword=q, page=page)
    return render_template("members.html", page=result, q=q)


@bp.route("/members/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        try:
            member_service.create_member(request.form)
        except DAOError as exc:
            flash_error(exc)
            return render_template("member_form.html", member=None, form=request.form), 400
        flash("会员已办理", "success")
        return redirect(url_for("members.list"))
    return render_template("member_form.html", member=None, form={})


@bp.route("/members/<member_id>/edit", methods=["GET", "POST"])
@login_required
def edit(member_id):
    member = member_service.get_member(member_id)
    if member is None:
        flash("会员不存在", "danger")
        return redirect(url_for("members.list"))

    if request.method == "POST":
        try:
            member_service.update_member(member_id, request.form)
        except DAOError as exc:
            flash_error(exc)
            return render_template("member_form.html", member=member, form=request.form), 400
        flash("会员信息已更新", "success")
        return redirect(url_for("members.list"))
    return render_template("member_form.html", member=member, form=member)


@bp.post("/members/<member_id>/points")
@login_required
def add_points(member_id):
    delta = parse_int(request.form.get("delta"), "积分变动")
    try:
        member_service.add_points(member_id, delta)
    except DAOError as exc:
        flash_error(exc)
    else:
        flash("积分已调整", "success")
    return redirect(url_for("members.edit", member_id=member_id))
