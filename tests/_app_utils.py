"""Shared helpers for DB-independent app-layer tests (成员B, 第9周).

The app services obtain the database through ``app.extensions.get_db()``, which
returns a module-level singleton.  Setting ``app.extensions._db`` to a
``FakeDB`` makes every service call DB-independent; the individual DAO classes
are mocked per-test with ``unittest.mock``.
"""

from __future__ import annotations

from contextlib import contextmanager


class FakeConn:
    """A stand-in for a pyodbc connection; services just pass it to DAOs."""


class FakeDB:
    """Minimal ``Database`` double exposing the three context-manager entry points."""

    def __init__(self) -> None:
        self.conn = FakeConn()

    @contextmanager
    def read(self, role: str):
        yield self.conn

    @contextmanager
    def auth_read(self):
        yield self.conn

    @contextmanager
    def transaction(self, role: str):
        yield self.conn

    def ping(self, role: str) -> bool:
        return True
