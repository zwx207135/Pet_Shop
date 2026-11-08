"""表单字符串到基础类型的转换（成员B 业务层校验入口）。

DAO 内部还会再次校验（``ensure_int`` / ``ensure_decimal`` / ``ensure_text``），
这里主要负责把 HTML 表单里的字符串转换成整数/金额，并给出友好错误。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from dao import DAOError, ErrorCode


def parse_int(value, field: str, *, default: int | None = None, minimum: int | None = None) -> int:
    if value is None or str(value).strip() == "":
        if default is not None:
            return default
        raise DAOError(ErrorCode.VALIDATION_ERROR, f"{field}不能为空")
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError):
        raise DAOError(ErrorCode.VALIDATION_ERROR, f"{field}必须是整数") from None
    if minimum is not None and result < minimum:
        raise DAOError(ErrorCode.VALIDATION_ERROR, f"{field}不能小于 {minimum}")
    return result


def parse_decimal(value, field: str, *, default: Decimal | None = None) -> Decimal:
    if value is None or str(value).strip() == "":
        if default is not None:
            return default
        raise DAOError(ErrorCode.VALIDATION_ERROR, f"{field}不能为空")
    try:
        return Decimal(str(value).strip())
    except InvalidOperation:
        raise DAOError(ErrorCode.VALIDATION_ERROR, f"{field}必须是数字") from None
