"""登录鉴权业务层测试（成员B，DB 无关，mock EmployeeDAO + get_db）。

覆盖：登录成功写 session、密码错误、账号不存在、账号停用、空输入、登出。
"""

from __future__ import annotations

import pytest
from flask import Flask, session

from dao import DAOError

from app.services import auth_service

# 与 sql/migration.sql 中种子密码一致的 scrypt 哈希（已单独用 check_password_hash 验证）
CLERK_HASH = (
    "scrypt:32768:8:1$f8nkO3RZhWJuTScQ$"
    "d5c807be3baff875bcb01c5147a58dcbe20498b854ee9c7941906faea1b6818d753861c031b8a30e5a2b5459379188a956bc07738216e31af2306bc543fc61de"
)


@pytest.fixture
def app():
    application = Flask(__name__)
    application.config["SECRET_KEY"] = "test"
    application.config["TESTING"] = True
    return application


@pytest.fixture
def fake_auth(monkeypatch):
    """替换 auth_service 的 get_db 与 EmployeeDAO，返回可编程的凭据。"""
    from tests._app_utils import FakeDB

    creds: dict = {}

    class _DAO:
        def get_credentials(self, conn, login_name):
            return creds.get(login_name)

    monkeypatch.setattr(auth_service, "get_db", lambda: FakeDB())
    monkeypatch.setattr(auth_service, "EmployeeDAO", lambda: _DAO())
    return creds


def _creds(role: str = "店员", is_active: bool = True) -> dict:
    return {
        "employee_id": "E002",
        "employee_name": "赵店员",
        "role": role,
        "login_name": "clerk",
        "password_hash": CLERK_HASH,
        "is_active": is_active,
    }


def test_login_success_writes_session(app, fake_auth):
    fake_auth["clerk"] = _creds()
    with app.test_request_context():
        cred = auth_service.login("clerk", "Clerk@123")
        assert cred["role"] == "店员"
        assert session["employee_id"] == "E002"
        assert session["role"] == "店员"
        assert session["login_name"] == "clerk"


def test_login_wrong_password_raises_unauth(app, fake_auth):
    fake_auth["clerk"] = _creds()
    with app.test_request_context():
        with pytest.raises(DAOError) as ei:
            auth_service.login("clerk", "wrong-password")
        assert ei.value.code == "UNAUTHENTICATED"


def test_login_unknown_account_raises_unauth(app, fake_auth):
    with app.test_request_context():
        with pytest.raises(DAOError) as ei:
            auth_service.login("ghost", "whatever")
        assert ei.value.code == "UNAUTHENTICATED"


def test_login_inactive_account_raises_unauth(app, fake_auth):
    fake_auth["clerk"] = _creds(is_active=False)
    with app.test_request_context():
        with pytest.raises(DAOError) as ei:
            auth_service.login("clerk", "Clerk@123")
        assert ei.value.code == "UNAUTHENTICATED"
        assert "停用" in ei.value.message


def test_login_empty_input_raises_validation(app, fake_auth):
    with app.test_request_context():
        with pytest.raises(DAOError) as ei:
            auth_service.login("", "")
        assert ei.value.code == "VALIDATION_ERROR"


def test_logout_clears_session(app):
    with app.test_request_context():
        session["employee_id"] = "E002"
        session["role"] = "店员"
        auth_service.logout()
        assert "employee_id" not in session
        assert "role" not in session
