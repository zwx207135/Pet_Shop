"""路由层公共辅助。"""

from __future__ import annotations

from flask import flash

from app.errors import log_error


def flash_error(error) -> None:
    """记录后端日志并把 DAOError 的友好文案通过 flash 展示给用户。"""
    log_error(error)
    flash(error.message, "danger")
