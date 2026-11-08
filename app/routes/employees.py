"""员工页面（成员B）。店长专属：店员连接会因数据库权限被拒绝。"""

from __future__ import annotations

from flask import Blueprint, render_template

from app.security import roles_required
from app.services import employee_service

bp = Blueprint("employees", __name__)


@bp.route("/employees")
@roles_required("店长")
def list():
    employees = employee_service.list_employees()
    return render_template("employees.html", employees=employees)
