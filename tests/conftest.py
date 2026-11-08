"""Shared pytest fixtures for DAO integration tests.

The suite runs against PetCareDB_test, a clone of PetCareDB created by
``scripts/create_test_db.py``.  Most tests open one manual-commit connection
and roll it back, so the seed data stays intact.
"""

from __future__ import annotations

import itertools
import os
import uuid
from decimal import Decimal

os.environ["DB_NAME"] = "PetCareDB_test"

import pyodbc
import pytest

from dao.config import DbConfig
from dao.database import Database
from dao.inventory_dao import InventoryDAO
from dao.product_dao import ProductDAO


@pytest.fixture(scope="session")
def config() -> DbConfig:
    config = DbConfig.from_env()
    if config.database != "PetCareDB_test":
        raise RuntimeError(
            f"DAO tests must run against PetCareDB_test, got {config.database!r}"
        )
    return config


@pytest.fixture(scope="session", autouse=True)
def clean_test_database(config: DbConfig):
    """Remove artefacts left by an interrupted earlier run."""

    def clean() -> None:
        conn = _connect(config, "manager", autocommit=True)
        try:
            cursor = conn.cursor()
            cursor.execute("SET LOCK_TIMEOUT 5000;")
            cursor.execute(
                "DELETE FROM dbo.InventoryLog WHERE remark LIKE ?;",
                ["pytest-%"],
            )
            cursor.execute(
                """
                DELETE FROM dbo.OrderDetail
                WHERE product_id IN (
                    SELECT product_id FROM dbo.Product
                    WHERE product_name LIKE ? AND category = ?
                );
                """,
                ["测试商品%", "测试"],
            )
            for table in ("InventoryLog", "Inventory"):
                cursor.execute(
                    f"""
                    DELETE FROM dbo.{table}
                    WHERE product_id IN (
                        SELECT product_id FROM dbo.Product
                        WHERE product_name LIKE ? AND category = ?
                    );
                    """,
                    ["测试商品%", "测试"],
                )
            cursor.execute(
                "DELETE FROM dbo.Product WHERE product_name LIKE ? AND category = ?;",
                ["测试商品%", "测试"],
            )
            cursor.execute(
                """
                DELETE FROM dbo.Orders
                WHERE order_id NOT IN ('O2025010101', 'O2025010102')
                  AND order_id NOT IN (SELECT order_id FROM dbo.OrderDetail);
                """
            )
            cursor.close()
        finally:
            conn.close()

    clean()
    yield
    clean()


@pytest.fixture(scope="session")
def db(config: DbConfig) -> Database:
    return Database(config)


def _connect(config: DbConfig, role: str, *, autocommit: bool = False) -> pyodbc.Connection:
    return pyodbc.connect(
        config.connection_string(role),
        autocommit=autocommit,
        timeout=config.timeout,
    )


@pytest.fixture
def clerk_conn(config: DbConfig):
    conn = _connect(config, "clerk")
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def manager_conn(config: DbConfig):
    conn = _connect(config, "manager")
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def auth_conn(config: DbConfig):
    conn = _connect(config, "auth", autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def purge_logs(config: DbConfig):
    """Delete committed inventory logs created by a test."""

    def purge(*remarks: str) -> None:
        conn = _connect(config, "manager", autocommit=True)
        try:
            cursor = conn.cursor()
            for remark in remarks:
                cursor.execute(
                    "DELETE FROM dbo.InventoryLog WHERE remark = ?;",
                    [remark],
                )
            cursor.close()
        finally:
            conn.close()

    return purge


@pytest.fixture
def product_factory(config: DbConfig):
    """Create committed products with inventory; clean them up afterwards."""
    product_ids: list[str] = []
    counter = itertools.count(1)

    def make(
        *,
        price: str = "10.00",
        quantity: int = 5,
        status: str = "在售",
        category: str = "测试",
    ) -> dict:
        name = f"测试商品{next(counter)}-{uuid.uuid4().hex[:6]}"
        conn = _connect(config, "manager")
        try:
            product = ProductDAO().create(
                conn,
                product_name=name,
                category=category,
                price=Decimal(price),
                stock_warn=1,
                status=status,
            )
            InventoryDAO().create(conn, product_id=product["product_id"], quantity=quantity)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
        product_ids.append(product["product_id"])
        return product

    yield make

    if not product_ids:
        return
    conn = _connect(config, "manager")
    try:
        cursor = conn.cursor()
        cursor.execute("SET LOCK_TIMEOUT 5000;")
        for product_id in product_ids:
            cursor.execute("DELETE FROM dbo.InventoryLog WHERE product_id = ?;", [product_id])
            cursor.execute("DELETE FROM dbo.OrderDetail WHERE product_id = ?;", [product_id])
            cursor.execute("DELETE FROM dbo.Inventory WHERE product_id = ?;", [product_id])
            cursor.execute("DELETE FROM dbo.Product WHERE product_id = ?;", [product_id])
        conn.commit()
        cursor.close()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
