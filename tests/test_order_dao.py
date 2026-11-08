from decimal import Decimal

import pyodbc
import pytest

from dao.errors import DAOError, ErrorCode, TransactionStateError
from dao.inventory_dao import InventoryDAO
from dao.models import OrderItemInput
from dao.order_dao import OrderDAO


@pytest.mark.integration
def test_create_order_merges_duplicate_items(clerk_conn):
    order = OrderDAO().create_with_details(
        clerk_conn,
        member_id="M001",
        employee_id="E002",
        pay_method="现金",
        items=[
            OrderItemInput("P002", 2),
            OrderItemInput("P001", 1),
            OrderItemInput("P002", 1),
        ],
    )

    assert order["order_id"].startswith("O") and len(order["order_id"]) == 12
    assert order["member_id"] == "M001"
    assert order["employee_id"] == "E002"
    assert order["total_amount"] == Decimal("187.70")
    assert [detail["product_id"] for detail in order["details"]] == ["P001", "P002"]
    assert order["details"][0]["quantity"] == 1
    assert order["details"][0]["subtotal"] == Decimal("128.00")
    assert order["details"][1]["quantity"] == 3
    assert order["details"][1]["subtotal"] == Decimal("59.70")

    assert InventoryDAO().get(clerk_conn, "P001")["quantity"] == 19
    assert InventoryDAO().get(clerk_conn, "P002")["quantity"] == 47

    logs = InventoryDAO().list_logs(clerk_conn, product_id="P002", change_type="销售")
    assert logs.total == 1
    assert logs.items[0]["change_qty"] == -3
    assert order["order_id"] in logs.items[0]["remark"]


@pytest.mark.integration
def test_create_order_without_member(clerk_conn):
    order = OrderDAO().create_with_details(
        clerk_conn,
        member_id=None,
        employee_id="E002",
        pay_method="微信",
        items=[OrderItemInput("P003", 1)],
    )
    assert order["member_id"] is None
    assert order["member_name"] == "散客"


@pytest.mark.integration
def test_insufficient_stock_aborts_before_writes(clerk_conn):
    with pytest.raises(DAOError) as excinfo:
        OrderDAO().create_with_details(
            clerk_conn,
            member_id=None,
            employee_id="E002",
            pay_method="现金",
            items=[OrderItemInput("P001", 1), OrderItemInput("P003", 9999)],
        )
    error = excinfo.value
    assert error.code == ErrorCode.BUSINESS_RULE_VIOLATION
    assert error.context == {"product_id": "P003", "available": 15, "requested": 9999}
    assert InventoryDAO().get(clerk_conn, "P001")["quantity"] == 20
    assert OrderDAO().list(clerk_conn).total == 2


@pytest.mark.integration
def test_missing_product(clerk_conn):
    with pytest.raises(DAOError) as excinfo:
        OrderDAO().create_with_details(
            clerk_conn,
            member_id=None,
            employee_id="E002",
            pay_method="现金",
            items=[OrderItemInput("P999", 1)],
        )
    assert excinfo.value.code == ErrorCode.NOT_FOUND


@pytest.mark.integration
def test_stopped_product_cannot_be_ordered(clerk_conn, product_factory):
    product = product_factory(status="停售")
    with pytest.raises(DAOError) as excinfo:
        OrderDAO().create_with_details(
            clerk_conn,
            member_id=None,
            employee_id="E002",
            pay_method="现金",
            items=[OrderItemInput(product["product_id"], 1)],
        )
    assert excinfo.value.code == ErrorCode.BUSINESS_RULE_VIOLATION
    assert "停售" in excinfo.value.message
    clerk_conn.rollback()


@pytest.mark.integration
def test_invalid_items(clerk_conn):
    dao = OrderDAO()
    with pytest.raises(DAOError) as excinfo:
        dao.create_with_details(
            clerk_conn, member_id=None, employee_id="E002", pay_method="现金", items=[]
        )
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR

    with pytest.raises(DAOError) as excinfo:
        dao.create_with_details(
            clerk_conn,
            member_id=None,
            employee_id="E002",
            pay_method="现金",
            items=[OrderItemInput("P001", 0)],
        )
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR

    with pytest.raises(DAOError) as excinfo:
        dao.create_with_details(
            clerk_conn,
            member_id=None,
            employee_id="E002",
            pay_method="现金",
            items=[{"product_id": "P001", "quantity": 1}],
        )
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR


@pytest.mark.integration
def test_unknown_employee_or_member(clerk_conn):
    dao = OrderDAO()
    with pytest.raises(DAOError) as excinfo:
        dao.create_with_details(
            clerk_conn,
            member_id=None,
            employee_id="E999",
            pay_method="现金",
            items=[OrderItemInput("P001", 1)],
        )
    assert excinfo.value.code == ErrorCode.CONFLICT_FOREIGN_KEY
    clerk_conn.rollback()

    with pytest.raises(DAOError) as excinfo:
        dao.create_with_details(
            clerk_conn,
            member_id="M999",
            employee_id="E002",
            pay_method="现金",
            items=[OrderItemInput("P001", 1)],
        )
    assert excinfo.value.code == ErrorCode.CONFLICT_FOREIGN_KEY


@pytest.mark.integration
def test_get_and_list(clerk_conn):
    dao = OrderDAO()
    order = dao.get(clerk_conn, "O2025010101")
    assert order is not None
    assert len(order["details"]) == 1
    assert order["details"][0]["product_id"] == "P001"
    assert order["total_amount"] == Decimal("128.00")

    header_only = dao.get(clerk_conn, "O2025010101", include_details=False)
    assert header_only is not None and "details" not in header_only
    assert dao.get(clerk_conn, "O2099010101") is None

    page = dao.list(clerk_conn, page_size=1)
    assert page.total == 2
    assert len(page.items) == 1
    assert dao.list(clerk_conn, member_id="M001").total == 1
    assert dao.list(clerk_conn, employee_id="E002").total == 2
    assert dao.list(clerk_conn, order_status="已完成").total == 2
    assert dao.list(clerk_conn, keyword="' OR 1=1 --").total == 0


@pytest.mark.integration
def test_update_status(clerk_conn):
    dao = OrderDAO()
    updated = dao.update_status(clerk_conn, "O2025010101", "未完成")
    assert updated is not None and updated["order_status"] == "未完成"
    assert dao.update_status(clerk_conn, "O2099010101", "未完成") is None


@pytest.mark.integration
def test_list_details(clerk_conn):
    details = OrderDAO().list_details(clerk_conn, "O2025010101")
    assert len(details) == 1
    assert details[0]["subtotal"] == Decimal("128.00")
    assert OrderDAO().list_details(clerk_conn, "O2099010101") == []


@pytest.mark.integration
def test_create_requires_transaction(config):
    conn = pyodbc.connect(config.connection_string("clerk"), autocommit=True)
    try:
        with pytest.raises(TransactionStateError):
            OrderDAO().create_with_details(
                conn,
                member_id=None,
                employee_id="E002",
                pay_method="现金",
                items=[OrderItemInput("P001", 1)],
            )
    finally:
        conn.close()
