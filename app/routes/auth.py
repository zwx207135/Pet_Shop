"""登录 / 登出页面。"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from dao import DAOError

from app.routes.common import flash_error
from app.security import current_user, login_required
from app.services import auth_service

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user() is not None:
        return redirect(url_for("main.index"))

    login_name = ""
    if request.method == "POST":
        login_name = request.form.get("login_name", "")
        password = request.form.get("password", "")
        try:
            auth_service.login(login_name, password)
        except DAOError as exc:
            flash_error(exc)
            return render_template("login.html", login_name=login_name), 401
        flash("登录成功", "success")
        nxt = request.form.get("next") or request.args.get("next")
        if nxt and nxt.startswith("/") and not nxt.startswith("//"):
            return redirect(nxt)
        return redirect(url_for("main.index"))
    return render_template("login.html", login_name=login_name)


@bp.post("/logout")
@login_required
def logout():
    auth_service.logout()
    flash("已退出登录", "info")
    return redirect(url_for("auth.login"))
