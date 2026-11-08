"""统一异常处理与后端日志（成员B）。"""

from .handlers import HTTP_STATUS, log_error, register_error_handlers

__all__ = ["HTTP_STATUS", "log_error", "register_error_handlers"]
