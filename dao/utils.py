"""Shared helpers for DAO modules."""

from __future__ import annotations

import functools
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable, Iterator, TypeVar

import pyodbc
from pyodbc import Connection, Cursor

from .errors import DAOError, ErrorCode, TransactionStateError, translate_pyodbc_error

F = TypeVar("F", bound=Callable[..., Any])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@contextmanager
def cursor_scope(conn: Connection) -> Iterator[Cursor]:
    """Close the cursor without touching the connection's transaction.

    ``with conn.cursor()`` calls ``commit()`` on exit in pyodbc, which would
    silently end the service layer's transaction, so DAO code must use this
    helper instead.
    """
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()


def validate_page(page: int, page_size: int) -> tuple[int, int]:
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        raise DAOError(
            ErrorCode.VALIDATION_ERROR,
            "页码必须是大于等于 1 的整数",
            context={"page": page},
        )
    if (
        not isinstance(page_size, int)
        or isinstance(page_size, bool)
        or page_size < 1
        or page_size > MAX_PAGE_SIZE
    ):
        raise DAOError(
            ErrorCode.VALIDATION_ERROR,
            f"每页条数必须在 1 到 {MAX_PAGE_SIZE} 之间",
            context={"page_size": page_size},
        )
    return page, page_size


def escape_like(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
        .replace("[", "\\[")
    )


def like_pattern(value: str) -> str:
    return f"%{escape_like(value)}%"


def rows_to_dicts(cursor: Cursor, rows: list[Any] | None = None) -> list[dict[str, Any]]:
    columns = [description[0] for description in cursor.description]
    data = cursor.fetchall() if rows is None else rows
    result: list[dict[str, Any]] = []
    for row in data:
        item: dict[str, Any] = {}
        for name, value in zip(columns, row):
            if isinstance(value, str):
                value = value.rstrip()
            item[name] = value
        result.append(item)
    return result


def row_to_dict(cursor: Cursor) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [description[0] for description in cursor.description]
    item: dict[str, Any] = {}
    for name, value in zip(columns, row):
        if isinstance(value, str):
            value = value.rstrip()
        item[name] = value
    return item


def require_transaction(conn: Connection) -> None:
    if bool(conn.autocommit):
        raise TransactionStateError(
            "该 DAO 方法必须在 Database.transaction() 的连接上调用",
            detail="connection.autocommit=True",
        )


def tx_cursor(conn: Connection) -> Cursor:
    require_transaction(conn)
    return conn.cursor()


def dao_errors(func: F) -> F:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except pyodbc.Error as exc:
            raise translate_pyodbc_error(exc) from exc

    return wrapper  # type: ignore[return-value]


def ensure_text(
    value: Any,
    field: str,
    *,
    max_length: int,
    required: bool = True,
) -> str | None:
    if value is None:
        if required:
            raise DAOError(
                ErrorCode.VALIDATION_ERROR,
                f"{field}不能为空",
                context={"field": field},
            )
        return None
    if not isinstance(value, str):
        raise DAOError(
            ErrorCode.VALIDATION_ERROR,
            f"{field}必须是字符串",
            context={"field": field},
        )
    cleaned = value.strip()
    if required and not cleaned:
        raise DAOError(
            ErrorCode.VALIDATION_ERROR,
            f"{field}不能为空",
            context={"field": field},
        )
    if len(cleaned) > max_length:
        raise DAOError(
            ErrorCode.VALIDATION_ERROR,
            f"{field}长度不能超过 {max_length} 个字符",
            context={"field": field, "max_length": max_length},
        )
    return cleaned


def ensure_int(value: Any, field: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise DAOError(
            ErrorCode.VALIDATION_ERROR,
            f"{field}必须是整数",
            context={"field": field},
        )
    if minimum is not None and value < minimum:
        raise DAOError(
            ErrorCode.VALIDATION_ERROR,
            f"{field}不能小于 {minimum}",
            context={"field": field, "minimum": minimum},
        )
    return value


def ensure_decimal(
    value: Any,
    field: str,
    *,
    minimum: Decimal | None = Decimal("0"),
) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float, str)):
        raise DAOError(
            ErrorCode.VALIDATION_ERROR,
            f"{field}必须是数字",
            context={"field": field},
        )
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise DAOError(
            ErrorCode.VALIDATION_ERROR,
            f"{field}必须是数字",
            context={"field": field},
        ) from None
    if not amount.is_finite():
        raise DAOError(
            ErrorCode.VALIDATION_ERROR,
            f"{field}必须是有限数字",
            context={"field": field},
        )
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if minimum is not None and amount < minimum:
        raise DAOError(
            ErrorCode.VALIDATION_ERROR,
            f"{field}不能小于 {minimum}",
            context={"field": field, "minimum": str(minimum)},
        )
    if abs(amount) >= Decimal("100000000"):
        raise DAOError(
            ErrorCode.VALIDATION_ERROR,
            f"{field}超出可存储范围",
            context={"field": field},
        )
    return amount


def ensure_choice(value: Any, field: str, allowed: set[str] | tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise DAOError(
            ErrorCode.VALIDATION_ERROR,
            f"{field}只能是 {' / '.join(allowed)} 之一",
            context={"field": field, "allowed": list(allowed)},
        )
    return value
