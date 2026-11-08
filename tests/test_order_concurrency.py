import threading
import time

import pyodbc
import pytest

from dao.errors import DAOError, ErrorCode
from dao.models import OrderItemInput
from dao.order_dao import OrderDAO


@pytest.mark.integration
def test_last_unit_cannot_be_sold_twice(config, product_factory):
    product = product_factory(quantity=1)
    product_id = product["product_id"]

    ready = threading.Event()
    results: dict[str, object] = {}

    def buyer_a() -> None:
        conn = pyodbc.connect(config.connection_string("clerk"), autocommit=False)
        try:
            results["a_order"] = OrderDAO().create_with_details(
                conn,
                member_id=None,
                employee_id="E002",
                pay_method="现金",
                items=[OrderItemInput(product_id, 1)],
            )
            ready.set()
            time.sleep(0.5)
            conn.commit()
        except BaseException as exc:  # pragma: no cover - failure path
            results["a_error"] = exc
            ready.set()
            conn.rollback()
        finally:
            conn.close()

    def buyer_b() -> None:
        ready.wait(timeout=5)
        conn = pyodbc.connect(config.connection_string("clerk"), autocommit=False)
        try:
            results["b_order"] = OrderDAO().create_with_details(
                conn,
                member_id=None,
                employee_id="E002",
                pay_method="现金",
                items=[OrderItemInput(product_id, 1)],
            )
            conn.commit()
        except DAOError as exc:
            results["b_error"] = exc
            conn.rollback()
        finally:
            conn.close()

    thread_a = threading.Thread(target=buyer_a)
    thread_b = threading.Thread(target=buyer_b)
    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=15)
    thread_b.join(timeout=15)

    assert "a_error" not in results, results.get("a_error")
    assert "a_order" in results
    assert "b_order" not in results
    error = results.get("b_error")
    assert isinstance(error, DAOError)
    assert error.code == ErrorCode.BUSINESS_RULE_VIOLATION
    assert error.context["product_id"] == product_id

    order = results["a_order"]
    cleanup = pyodbc.connect(config.connection_string("manager"), autocommit=True)
    try:
        cursor = cleanup.cursor()
        cursor.execute("DELETE FROM dbo.OrderDetail WHERE order_id = ?;", [order["order_id"]])
        cursor.execute("DELETE FROM dbo.Orders WHERE order_id = ?;", [order["order_id"]])
        cursor.close()
    finally:
        cleanup.close()
