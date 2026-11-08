"""登录鉴权（成员B）。"""

from __future__ import annotations

from flask import session
from werkzeug.security import check_password_hash

from dao import DAOError, EmployeeDAO, ErrorCode

from app.extensions import get_db


def login(login_name: str, password: str) -> dict:
    """校验登录名/密码，成功后写入 session。

    只通过 ``db.auth_read()`` 读取凭据视图，业务连接与登录连接彻底分离。
    密码校验使用 werkzeug ``check_password_hash``（scrypt）。
    """
    login_name = (login_name or "").strip()
    if not login_name or not password:
        raise DAOError(ErrorCode.VALIDATION_ERROR, "请输入用户名和密码")

    with get_db().auth_read() as conn:
        cred = EmployeeDAO().get_credentials(conn, login_name)

    if cred is None:
        raise DAOError(ErrorCode.UNAUTHENTICATED, "用户名或密码错误")
    if not cred.get("is_active"):
        raise DAOError(ErrorCode.UNAUTHENTICATED, "账号已停用，请联系管理员")
    if not check_password_hash(cred["password_hash"], password):
        raise DAOError(ErrorCode.UNAUTHENTICATED, "用户名或密码错误")

    session["employee_id"] = cred["employee_id"]
    session["employee_name"] = cred["employee_name"]
    session["role"] = cred["role"]  # 「店长」/「店员」
    session["login_name"] = cred["login_name"]
    return cred


def logout() -> None:
    session.clear()
