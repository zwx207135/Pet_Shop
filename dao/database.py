"""Connection and transaction entry points."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

import pyodbc

from .config import DbConfig
from .errors import (
    DAOError,
    ErrorCode,
    TransactionStateError,
    translate_pyodbc_error,
)


class Database:
    """Owns SQL Server connections; the service layer owns the transaction boundary."""

    def __init__(self, config: DbConfig) -> None:
        self.config = config
        self._local = threading.local()

    @property
    def _depth(self) -> int:
        return getattr(self._local, "depth", 0)

    @_depth.setter
    def _depth(self, value: int) -> None:
        self._local.depth = value

    def _connect(self, role: str, *, autocommit: bool) -> pyodbc.Connection:
        try:
            return pyodbc.connect(
                self.config.connection_string(role),
                autocommit=autocommit,
                timeout=self.config.timeout,
            )
        except pyodbc.Error as exc:
            raise translate_pyodbc_error(exc) from exc

    @contextmanager
    def read(self, role: str) -> Iterator[pyodbc.Connection]:
        conn = self._connect(role, autocommit=True)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def auth_read(self) -> Iterator[pyodbc.Connection]:
        conn = self._connect("auth", autocommit=True)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self, role: str) -> Iterator[pyodbc.Connection]:
        if self._depth:
            raise TransactionStateError(
                "transaction() 不支持嵌套",
                detail=f"active_depth={self._depth}",
            )

        conn = self._connect(role, autocommit=False)
        self._depth += 1
        try:
            try:
                cursor = conn.cursor()
                cursor.execute("SET XACT_ABORT ON;")
                cursor.close()
            except pyodbc.Error as exc:
                raise translate_pyodbc_error(exc) from exc

            try:
                yield conn
            except BaseException:
                try:
                    conn.rollback()
                except pyodbc.Error:
                    pass
                raise
            else:
                try:
                    conn.commit()
                except pyodbc.Error as exc:
                    try:
                        conn.rollback()
                    except pyodbc.Error:
                        pass
                    raise DAOError(
                        ErrorCode.TRANSACTION_FAILED,
                        detail=str(exc),
                    ) from exc
        finally:
            self._depth -= 1
            conn.close()

    def ping(self, role: str) -> bool:
        try:
            with self.read(role) as conn:
                conn.cursor().execute("SELECT 1;").fetchone()
            return True
        except (DAOError, pyodbc.Error):
            return False
