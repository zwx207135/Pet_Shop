from decimal import Decimal

import pyodbc
import pytest

from dao.errors import DAOError, ErrorCode, translate_pyodbc_error
from dao.ids import next_id
from dao.product_dao import ProductDAO


@pytest.mark.integration
def test_clerk_allowed_reads(clerk_conn):
    cursor = clerk_conn.cursor()
    for sql in (
        "SELECT TOP 1 product_id FROM dbo.Product;",
        "SELECT TOP 1 product_id FROM dbo.Inventory;",
        "SELECT TOP 1 order_id FROM dbo.v_order_header;",
        "SELECT TOP 1 order_id FROM dbo.v_order_detail;",
        "SELECT TOP 1 product_id FROM dbo.v_product_sales;",
        "SELECT TOP 1 product_id FROM dbo.v_inventory_status;",
        "SELECT TOP 1 member_id FROM dbo.v_member_consumption;",
        "SELECT TOP 1 appointment_id FROM dbo.v_service_appointment;",
    ):
        cursor.execute(sql).fetchone()
    cursor.close()


@pytest.mark.integration
def test_clerk_can_use_order_sequences(clerk_conn):
    order_id = next_id(clerk_conn, "order")
    detail_id = next_id(clerk_conn, "order_detail")
    log_id = next_id(clerk_conn, "inventory_log")
    member_id = next_id(clerk_conn, "member")
    assert order_id.startswith("O") and len(order_id) == 12
    assert detail_id.startswith("D") and len(detail_id) == 10
    assert log_id.startswith("L") and len(log_id) == 10
    assert member_id.startswith("M") and len(member_id) == 8


@pytest.mark.integration
def test_clerk_cannot_use_product_sequence(clerk_conn):
    with pytest.raises(DAOError) as excinfo:
        next_id(clerk_conn, "product")
    assert excinfo.value.code == ErrorCode.FORBIDDEN


@pytest.mark.integration
def test_clerk_cannot_modify_products(clerk_conn):
    with pytest.raises(DAOError) as excinfo:
        ProductDAO().update(clerk_conn, "P001", {"price": Decimal("1.00")})
    assert excinfo.value.code == ErrorCode.FORBIDDEN

    with pytest.raises(DAOError) as excinfo:
        ProductDAO().delete(clerk_conn, "P003")
    assert excinfo.value.code == ErrorCode.FORBIDDEN


@pytest.mark.integration
def test_clerk_cannot_read_employee_table(clerk_conn):
    with pytest.raises(pyodbc.Error) as excinfo:
        clerk_conn.cursor().execute(
            "SELECT TOP 1 employee_id FROM dbo.Employee;"
        ).fetchone()
    assert translate_pyodbc_error(excinfo.value).code == ErrorCode.FORBIDDEN


@pytest.mark.integration
def test_manager_can_manage_products(manager_conn):
    dao = ProductDAO()
    product = dao.create(
        manager_conn,
        product_name="权限测试商品",
        category="测试",
        price=Decimal("3.00"),
    )
    assert dao.update(manager_conn, product["product_id"], {"price": Decimal("4.00")})[
        "price"
    ] == Decimal("4.00")
    assert dao.delete(manager_conn, product["product_id"]) is True


@pytest.mark.integration
def test_manager_can_use_product_sequence(manager_conn):
    product_id = next_id(manager_conn, "product")
    assert product_id.startswith("P") and len(product_id) == 8
