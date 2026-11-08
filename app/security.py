"""登录态与角色权限控制（成员B 业务层的访问控制基础）。

- 登录成功后 session 中保存 ``employee_id`` / ``employee_name`` / ``role`` / ``login_name``；
- ``role`` 取业务口径「店长」/「店员」，通过 ``db_role()`` 映射到数据库角色
  ``manager`` / ``clerk``；
- ``login_required`` 只要求登录，``roles_required`` 额外要求角色。
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from flask import flash, redirect, request, session, url_for

F = TypeVar("F", bound=Callable)

# 业务角色 -> 数据库角色
ROLE_TO_DB_ROLE = {"店长": "manager", "店员": "clerk"}


def current_user() -> dict | None:
    """返回当前登录用户信息；未登录返回 None。"""
    if "employee_id" not in session:
        return None
    return {
        "employee_id": session["employee_id"],
        "employee_name": session.get("employee_name", ""),
        "role": session.get("role", ""),
        "login_name": session.get("login_name", ""),
    }


def db_role() -> str:
    """把业务角色映射为数据库角色，未登录默认 ``clerk``（只读安全兜底）。"""
    return ROLE_TO_DB_ROLE.get(session.get("role", ""), "clerk")


def login_required(view: F) -> F:
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped  # type: ignore[return-value]


def roles_required(*roles: str) -> Callable[[F], F]:
    """要求当前用户角色属于 ``roles``，否则拒绝并提示。"""

    def decorator(view: F) -> F:
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_user() is None:
                return redirect(url_for("auth.login", next=request.path))
            if session.get("role") not in roles:
                flash("没有执行该操作的权限", "danger")
                return redirect(url_for("main.index"))
            return view(*args, **kwargs)

        return wrapped  # type: ignore[return-value]

    return decorator
