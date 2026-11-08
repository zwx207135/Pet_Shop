"""登录态与角色权限装饰器测试（成员B，DB 无关）。

覆盖：
- ``login_required``：未登录访问受保护页 -> 302 重定向到登录页（带 next）；
- ``roles_required``：店员访问店长专属路由 -> 302 重定向首页 + 友好 flash；
- 店长访问店长专属路由 -> 正常放行。
"""

from __future__ import annotations

import pytest
from flask import Flask, get_flashed_messages, session

from app.security import login_required, roles_required


@pytest.fixture
def app():
    application = Flask(__name__)
    application.config["SECRET_KEY"] = "test"
    application.config["TESTING"] = True

    @application.route("/login", endpoint="auth.login")
    def login():
        return "login-page"

    @application.route("/", endpoint="main.index")
    def index():
        msgs = [m[1] for m in get_flashed_messages(with_categories=True)]
        return "home " + " ".join(msgs)

    @application.route("/protected")
    @login_required
    def protected():
        return "protected-content"

    @application.route("/manager-only")
    @roles_required("店长")
    def manager_only():
        return "manager-content"

    return application


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, role):
    with client.session_transaction() as sess:
        sess["employee_id"] = "E001" if role == "店长" else "E002"
        sess["employee_name"] = "王店长" if role == "店长" else "赵店员"
        sess["role"] = role
        sess["login_name"] = "manager" if role == "店长" else "clerk"


def test_unauthenticated_redirects_to_login_with_next(client):
    resp = client.get("/protected")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert "next=%2Fprotected" in resp.headers["Location"] or "next=/protected" in resp.headers["Location"]


def test_authenticated_user_can_access(client):
    _login(client, "店员")
    resp = client.get("/protected")
    assert resp.status_code == 200
    assert b"protected-content" in resp.data


def test_clerk_blocked_from_manager_route(client):
    _login(client, "店员")
    resp = client.get("/manager-only", follow_redirects=True)
    assert resp.status_code == 200  # 重定向到首页
    # 友好提示 flash
    assert "没有执行该操作的权限" in resp.get_data(as_text=True)


def test_manager_allowed_on_manager_route(client):
    _login(client, "店长")
    resp = client.get("/manager-only")
    assert resp.status_code == 200
    assert b"manager-content" in resp.data


def test_unauthenticated_manager_route_redirects_to_login(client):
    resp = client.get("/manager-only")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
