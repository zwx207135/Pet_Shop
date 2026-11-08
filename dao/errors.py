"""Unified DAO error types and pyodbc error translation."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

import pyodbc


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    CONFLICT_UNIQUE = "CONFLICT_UNIQUE"
    CONFLICT_FOREIGN_KEY = "CONFLICT_FOREIGN_KEY"
    CONFLICT_CHECK = "CONFLICT_CHECK"
    DB_UNAVAILABLE = "DB_UNAVAILABLE"
    DB_TIMEOUT = "DB_TIMEOUT"
    TRANSACTION_FAILED = "TRANSACTION_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_DEFAULT_MESSAGES: dict[str, str] = {
    ErrorCode.VALIDATION_ERROR.value: "输入数据不合法",
    ErrorCode.UNAUTHENTICATED.value: "请先登录",
    ErrorCode.FORBIDDEN.value: "没有执行该操作的权限",
    ErrorCode.NOT_FOUND.value: "记录不存在",
    ErrorCode.BUSINESS_RULE_VIOLATION.value: "操作违反业务规则",
    ErrorCode.CONFLICT_UNIQUE.value: "数据已存在，不能重复",
    ErrorCode.CONFLICT_FOREIGN_KEY.value: "记录被其他数据引用，无法操作",
    ErrorCode.CONFLICT_CHECK.value: "数据不满足约束条件",
    ErrorCode.DB_UNAVAILABLE.value: "数据库暂时不可用",
    ErrorCode.DB_TIMEOUT.value: "数据库响应超时，请稍后重试",
    ErrorCode.TRANSACTION_FAILED.value: "事务执行失败",
    ErrorCode.INTERNAL_ERROR.value: "系统内部错误",
}


class DAOError(Exception):
    """The only exception type DAO code raises towards the service layer."""

    def __init__(
        self,
        code: ErrorCode | str,
        message: str | None = None,
        *,
        context: dict[str, Any] | None = None,
        detail: str | None = None,
        retryable: bool = False,
    ) -> None:
        value = code.value if isinstance(code, ErrorCode) else str(code)
        if value not in _DEFAULT_MESSAGES:
            value = ErrorCode.INTERNAL_ERROR.value
        self.code: str = value
        self.message: str = message or _DEFAULT_MESSAGES[value]
        self.context: dict[str, Any] | None = context
        self.detail: str | None = detail
        self.retryable: bool = retryable
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class TransactionStateError(DAOError):
    """Raised when transaction() is nested or misused."""

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(
            ErrorCode.TRANSACTION_FAILED,
            message,
            detail=detail,
        )


_NATIVE_CODE_RE = re.compile(r"\((-?\d+)\)")
_DEADLOCK_CODES = {-2, 1205}
_UNAVAILABLE_CODES = {4060, 4061, 18452, 18456, 233, 10054}
_VALIDATION_CODES = {245, 515, 2628, 8114, 8115, 8152}
_INTERNAL_CODES = {207, 208, 2812}
_UNIQUE_CODES = {2601, 2627}
_FORBIDDEN_CODES = {229, 230}


def _native_codes(text: str) -> set[int]:
    return {int(match) for match in _NATIVE_CODE_RE.findall(text)}


def translate_pyodbc_error(exc: Exception) -> DAOError:
    """Map a pyodbc / SQL Server exception to a DAOError.

    The original text is preserved in ``detail`` for backend logging only; it is
    never used as the user-facing message.
    """
    if isinstance(exc, DAOError):
        return exc

    args = [str(arg) for arg in getattr(exc, "args", ())]
    raw = " ".join(args) or str(exc)
    lowered = raw.lower()
    sqlstate = args[0].strip().upper() if args else ""
    natives = _native_codes(raw)

    if natives & _DEADLOCK_CODES or sqlstate in {"40001", "HYT00", "HYT01"}:
        return DAOError(ErrorCode.DB_TIMEOUT, detail=raw, retryable=True)

    if natives & _UNAVAILABLE_CODES or sqlstate.startswith("08") or sqlstate == "28000":
        return DAOError(ErrorCode.DB_UNAVAILABLE, detail=raw)

    if isinstance(exc, pyodbc.InterfaceError):
        return DAOError(ErrorCode.DB_UNAVAILABLE, detail=raw)

    if natives & _UNIQUE_CODES or (
        sqlstate == "23000" and ("unique" in lowered or "duplicate key" in lowered)
    ):
        return DAOError(ErrorCode.CONFLICT_UNIQUE, detail=raw)

    if 547 in natives or (sqlstate == "23000" and "constraint" in lowered):
        if "foreign key" in lowered or "reference" in lowered:
            return DAOError(ErrorCode.CONFLICT_FOREIGN_KEY, detail=raw)
        if "check" in lowered:
            return DAOError(ErrorCode.CONFLICT_CHECK, detail=raw)
        return DAOError(ErrorCode.CONFLICT_CHECK, detail=raw)

    if natives & _FORBIDDEN_CODES:
        return DAOError(ErrorCode.FORBIDDEN, detail=raw)

    if natives & _VALIDATION_CODES or sqlstate in {"22001", "22003", "22018"}:
        return DAOError(ErrorCode.VALIDATION_ERROR, detail=raw)

    if natives & _INTERNAL_CODES:
        return DAOError(ErrorCode.INTERNAL_ERROR, detail=raw)

    if isinstance(exc, pyodbc.OperationalError):
        return DAOError(ErrorCode.DB_UNAVAILABLE, detail=raw)

    return DAOError(ErrorCode.INTERNAL_ERROR, detail=raw)
