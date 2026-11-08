"""统一异常处理与后端日志结构的单元测试（成员B，DB 无关）。

覆盖 DAO 契约 3.2 / 3.4：
- 错误码 -> HTTP 状态码映射；
- ``Accept: application/json`` 返回统一 JSON 结构；
- HTML 请求渲染错误页、只展示友好 message、不泄漏 detail；
- 后端日志记录 request_id / operation / role / code / detail。
"""

from __future__ import annotations

import logging

import pytest

from dao import DAOError, ErrorCode

from app import create_app


@pytest.fixture
def app():
    application = create_app()
    application.config["TESTING"] = True

    @application.route("/_err/<code>")
    def raise_by_code(code):
        raise DAOError(code, f"友好提示-{code}", detail="服务器内部细节")

    @application.route("/_err/custom")
    def raise_custom():
        raise DAOError(ErrorCode.BUSINESS_RULE_VIOLATION, "库存不足", context={"available": 2, "requested": 3})

    return application


@pytest.fixture
def client(app):
    return app.test_client()


STATUS_MAP = [
    ("VALIDATION_ERROR", 400),
    ("UNAUTHENTICATED", 401),
    ("FORBIDDEN", 403),
    ("NOT_FOUND", 404),
    ("BUSINESS_RULE_VIOLATION", 409),
    ("CONFLICT_UNIQUE", 409),
    ("CONFLICT_FOREIGN_KEY", 409),
    ("CONFLICT_CHECK", 409),
    ("DB_UNAVAILABLE", 503),
    ("DB_TIMEOUT", 503),
    ("TRANSACTION_FAILED", 500),
    ("INTERNAL_ERROR", 500),
]


@pytest.mark.parametrize("code,status", STATUS_MAP)
def test_error_code_to_http_status(client, code, status):
    resp = client.get(f"/_err/{code}", headers={"Accept": "application/json"})
    assert resp.status_code == status


def test_json_response_structure(client):
    resp = client.get("/_err/custom", headers={"Accept": "application/json"})
    assert resp.status_code == 409
    body = resp.get_json()
    assert set(body.keys()) == {"ok", "code", "message", "data", "request_id"}
    assert body["ok"] is False
    assert body["code"] == "BUSINESS_RULE_VIOLATION"
    assert body["message"] == "库存不足"
    assert body["data"] is None
    assert isinstance(body["request_id"], str) and len(body["request_id"]) == 12


def test_html_error_page_does_not_leak_detail(client):
    resp = client.get("/_err/BUSINESS_RULE_VIOLATION")
    assert resp.status_code == 409
    # 页面显示友好文案与错误码，但不泄漏 detail / 堆栈
    assert "友好提示-BUSINESS_RULE_VIOLATION" in resp.text
    assert "BUSINESS_RULE_VIOLATION" in resp.text
    assert "服务器内部细节" not in resp.text
    assert "Traceback" not in resp.text


def test_json_error_does_not_leak_detail(client):
    resp = client.get("/_err/FORBIDDEN", headers={"Accept": "application/json"})
    body = resp.get_json()
    assert "服务器内部细节" not in str(body)
    assert "detail" not in body


def test_backend_log_structure(client, caplog):
    # petcare.web 默认 propagate=False（日志只写文件/终端），此处临时放开传播，
    # 让 caplog 捕获到记录，验证字段结构。
    web_logger = logging.getLogger("petcare.web")
    with caplog.at_level(logging.ERROR, logger="petcare.web"):
        web_logger.propagate = True
        try:
            client.get("/_err/FORBIDDEN", headers={"Accept": "application/json"})
        finally:
            web_logger.propagate = False

    error_records = [r for r in caplog.records if r.getMessage().startswith("error ")]
    assert error_records, "should have logged an 'error ...' record"
    msg = error_records[0].getMessage()
    assert "request_id=" in msg
    assert "operation=raise_by_code" in msg
    assert "role=-" in msg  # 未登录，session 无角色
    assert "code=FORBIDDEN" in msg
    assert "detail='服务器内部细节'" in msg


def test_request_outcome_logged(client, caplog):
    web_logger = logging.getLogger("petcare.web")
    with caplog.at_level(logging.INFO, logger="petcare.web"):
        web_logger.propagate = True
        try:
            client.get("/_err/custom", headers={"Accept": "application/json"})
        finally:
            web_logger.propagate = False
    info_records = [r for r in caplog.records if r.getMessage().startswith("request_id=")]
    assert info_records, "should log a request outcome line"
    assert "status=409" in info_records[0].getMessage()
