from datetime import datetime, timedelta

import pytest

from dao.errors import DAOError, ErrorCode
from dao.inventory_dao import InventoryDAO
from dao.product_dao import ProductDAO


@pytest.mark.integration
def test_get_inventory(clerk_conn):
    row = InventoryDAO().get(clerk_conn, "P001")
    assert row is not None
    assert row["product_id"] == "P001"
    assert row["quantity"] == 20
    assert row["stock_status"] == "正常"
    assert InventoryDAO().get(clerk_conn, "P999") is None


@pytest.mark.integration
def test_list_and_low_stock_filter(clerk_conn):
    dao = InventoryDAO()
    page = dao.list(clerk_conn)
    assert page.total == 3
    assert [item["product_id"] for item in page.items] == ["P001", "P002", "P003"]
    assert dao.list(clerk_conn, low_stock_only=True).total == 0
    assert dao.list(clerk_conn, keyword="P002").total == 1


@pytest.mark.integration
def test_low_stock_detection(clerk_conn, product_factory):
    product = product_factory(quantity=0)
    page = InventoryDAO().list(clerk_conn, low_stock_only=True)
    assert any(item["product_id"] == product["product_id"] for item in page.items)
    row = InventoryDAO().get(clerk_conn, product["product_id"])
    assert row is not None and row["stock_status"] == "缺货"


@pytest.mark.integration
def test_create_writes_initial_log(manager_conn):
    product = ProductDAO().create(
        manager_conn,
        product_name="库存初始化商品",
        category=None,
        price="5.00",
    )
    created = InventoryDAO().create(
        manager_conn,
        product_id=product["product_id"],
        quantity=4,
        remark="pytest-init",
    )
    assert created["quantity"] == 4
    logs = InventoryDAO().list_logs(manager_conn, product_id=product["product_id"])
    assert logs.total == 1
    assert logs.items[0]["change_type"] == "入库"
    assert logs.items[0]["change_qty"] == 4


@pytest.mark.integration
def test_duplicate_inventory_conflicts(manager_conn):
    with pytest.raises(DAOError) as excinfo:
        InventoryDAO().create(manager_conn, product_id="P001", quantity=1)
    assert excinfo.value.code == ErrorCode.CONFLICT_UNIQUE


@pytest.mark.integration
def test_adjust_in_and_out(clerk_conn):
    dao = InventoryDAO()
    inbound = dao.adjust(
        clerk_conn, "P003", change_qty=5, change_type="入库", remark="pytest-in"
    )
    assert inbound["quantity_before"] == 15
    assert inbound["quantity_after"] == 20
    assert inbound["log_id"].startswith("L")

    outbound = dao.adjust(
        clerk_conn, "P003", change_qty=-2, change_type="销售", remark="pytest-out"
    )
    assert outbound["quantity_before"] == 20
    assert outbound["quantity_after"] == 18

    logs = dao.list_logs(clerk_conn, product_id="P003")
    assert logs.total == 2
    assert logs.items[0]["remark"] == "pytest-out"


@pytest.mark.integration
def test_adjust_insufficient_stock(clerk_conn):
    with pytest.raises(DAOError) as excinfo:
        InventoryDAO().adjust(
            clerk_conn, "P003", change_qty=-999, change_type="销售", remark="pytest-short"
        )
    error = excinfo.value
    assert error.code == ErrorCode.BUSINESS_RULE_VIOLATION
    assert error.context == {"product_id": "P003", "available": 15, "requested": 999}


@pytest.mark.integration
def test_adjust_rejects_zero_and_sign_mismatch(clerk_conn):
    dao = InventoryDAO()
    with pytest.raises(DAOError) as excinfo:
        dao.adjust(clerk_conn, "P003", change_qty=0, change_type="入库")
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR

    with pytest.raises(DAOError):
        dao.adjust(clerk_conn, "P003", change_qty=-1, change_type="入库")
    with pytest.raises(DAOError):
        dao.adjust(clerk_conn, "P003", change_qty=1, change_type="销售")


@pytest.mark.integration
def test_adjust_missing_inventory(clerk_conn):
    with pytest.raises(DAOError) as excinfo:
        InventoryDAO().adjust(clerk_conn, "P999", change_qty=1, change_type="入库")
    assert excinfo.value.code == ErrorCode.NOT_FOUND


@pytest.mark.integration
def test_set_warn_requires_product_update(manager_conn, clerk_conn):
    updated = InventoryDAO().set_warn(manager_conn, "P003", 7)
    assert updated is not None and updated["stock_warn"] == 7
    assert InventoryDAO().set_warn(manager_conn, "P999", 7) is None

    with pytest.raises(DAOError) as excinfo:
        InventoryDAO().set_warn(clerk_conn, "P003", 7)
    assert excinfo.value.code == ErrorCode.FORBIDDEN


@pytest.mark.integration
def test_list_logs_filters_and_pagination(clerk_conn):
    dao = InventoryDAO()
    all_logs = dao.list_logs(clerk_conn, page_size=2)
    assert all_logs.total == 3
    assert len(all_logs.items) == 2

    sales = dao.list_logs(clerk_conn, change_type="销售")
    assert sales.total == 1
    assert sales.items[0]["product_id"] == "P001"

    now = datetime.now()
    assert dao.list_logs(clerk_conn, start=now + timedelta(days=1)).total == 0

    with pytest.raises(DAOError) as excinfo:
        dao.list_logs(clerk_conn, start=now, end=now - timedelta(days=1))
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR
