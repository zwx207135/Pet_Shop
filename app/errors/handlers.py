"""把 DAO 统一错误转换为 HTTP 响应，并写入后端日志。

DAO 契约 3.2 / 3.4：
- 错误码到 HTTP 状态码的映射；
- 统一 JSON 响应格式（HTML 页面使用 flash 展示 message）；
- 后端日志记录 request_id、操作名称、用户角色、错误码、detail 与处理结果。
"""

from __future__ import annotations

import logging
import uuid

from flask import Flask, g, jsonify, render_template, request, session
from werkzeug.exceptions import HTTPException

from dao import DAOError

logger = logging.getLogger("petcare.web")

HTTP_STATUS: dict[str, int] = {
    "VALIDATION_ERROR": 400,
    "UNAUTHENTICATED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "BUSINESS_RULE_VIOLATION": 409,
    "CONFLICT_UNIQUE": 409,
    "CONFLICT_FOREIGN_KEY": 409,
    "CONFLICT_CHECK": 409,
    "DB_UNAVAILABLE": 503,
    "DB_TIMEOUT": 503,
    "TRANSACTION_FAILED": 500,
    "INTERNAL_ERROR": 500,
}


def log_error(error: DAOError) -> str:
    """记录一条 DAOError，返回 request_id 供响应复用。"""
    request_id = str(g.get("request_id", "-"))
    logger.error(
        "error request_id=%s operation=%s role=%s code=%s message=%r detail=%r",
        request_id,
        g.get("operation", "-"),
        session.get("role", "-"),
        error.code,
        error.message,
        error.detail,
    )
    return request_id


def _wants_json() -> bool:
    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/html" not in accept


def _error_payload(code: str, message: str) -> dict:
    return {
        "ok": False,
        "code": code,
        "message": message,
        "data": None,
        "request_id": g.get("request_id"),
    }


def register_error_handlers(app: Flask) -> None:
    @app.before_request
    def assign_request_id() -> None:
        g.request_id = uuid.uuid4().hex[:12]
        g.operation = request.endpoint or request.path

    @app.after_request
    def log_outcome(response):
        logger.info(
            "request_id=%s method=%s path=%s endpoint=%s role=%s status=%s",
            g.get("request_id", "-"),
            request.method,
            request.path,
            g.get("operation", "-"),
            session.get("role", "-"),
            response.status_code,
        )
        return response

    @app.errorhandler(DAOError)
    def handle_dao_error(error: DAOError):
        request_id = log_error(error)
        status = HTTP_STATUS.get(error.code, 500)
        if _wants_json():
            payload = _error_payload(error.code, error.message)
            payload["request_id"] = request_id
            return jsonify(payload), status
        return render_template("error.html", status=status, error=error), status

    @app.errorhandler(404)
    def handle_not_found(error):
        logger.warning(
            "request_id=%s operation=%s 404 path=%s",
            g.get("request_id", "-"),
            g.get("operation", "-"),
            request.path,
        )
        if _wants_json():
            return jsonify(_error_payload("NOT_FOUND", "页面不存在")), 404
        return render_template("error.html", status=404, error=None), 404

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        logger.warning(
            "request_id=%s operation=%s http_exception=%s path=%s",
            g.get("request_id", "-"),
            g.get("operation", "-"),
            error.code,
            request.path,
        )
        if _wants_json():
            return jsonify(_error_payload("HTTP_ERROR", error.name)), error.code
        return render_template("error.html", status=error.code, error=None), error.code

    @app.errorhandler(Exception)
    def handle_uncaught(error):
        request_id = str(g.get("request_id", "-"))
        logger.exception(
            "request_id=%s operation=%s role=%s uncaught=%r",
            request_id,
            g.get("operation", "-"),
            session.get("role", "-"),
            error,
        )
        if _wants_json():
            return jsonify(_error_payload("INTERNAL_ERROR", "系统内部错误")), 500
        return render_template("error.html", status=500, error=None), 500
