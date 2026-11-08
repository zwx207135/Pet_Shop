from decimal import Decimal

import pytest

from dao.errors import DAOError, ErrorCode
from dao.product_dao import ProductDAO


@pytest.mark.integration
def test_list_and_pagination(clerk_conn):
    dao = ProductDAO()
    first = dao.list(clerk_conn, page=1, page_size=2)
    assert first.total == 3
    assert len(first.items) == 2
    assert first.items[0]["product_id"] == "P001"
    assert isinstance(first.items[0]["price"], Decimal)

    second = dao.list(clerk_conn, page=2, page_size=2)
    assert second.total == 3
    assert len(second.items) == 1
    assert second.items[0]["product_id"] == "P003"


@pytest.mark.integration
def test_list_filters(clerk_conn):
    dao = ProductDAO()
    assert dao.list(clerk_conn, status="在售").total == 3
    assert dao.list(clerk_conn, status="停售").total == 0
    category = dao.list(clerk_conn, page_size=1).items[0]["category"]
    assert dao.list(clerk_conn, category=category).total >= 1


@pytest.mark.integration
def test_list_invalid_pagination(clerk_conn):
    with pytest.raises(DAOError) as excinfo:
        ProductDAO().list(clerk_conn, page=0)
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR


@pytest.mark.integration
def test_keyword_is_parameterized(clerk_conn):
    assert ProductDAO().list(clerk_conn, keyword="' OR 1=1 --").total == 0


@pytest.mark.integration
def test_get_existing_and_missing(clerk_conn):
    dao = ProductDAO()
    product = dao.get(clerk_conn, "P001")
    assert product is not None
    assert product["product_id"] == "P001"
    assert product["price"] == Decimal("128.00")
    assert dao.get(clerk_conn, "P999") is None


@pytest.mark.integration
def test_create_product(manager_conn):
    dao = ProductDAO()
    product = dao.create(
        manager_conn,
        product_name="测试创建商品",
        category="测试",
        price=Decimal("12.30"),
        stock_warn=3,
    )
    assert len(product["product_id"]) == 8
    assert product["product_id"].startswith("P")
    assert product["price"] == Decimal("12.30")
    assert product["status"] == "在售"
    assert dao.get(manager_conn, product["product_id"]) == product


@pytest.mark.integration
def test_create_rejects_invalid_price(manager_conn):
    with pytest.raises(DAOError) as excinfo:
        ProductDAO().create(
            manager_conn,
            product_name="负价商品",
            category=None,
            price=Decimal("-1"),
        )
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR


@pytest.mark.integration
def test_update_and_unknown_field(manager_conn):
    dao = ProductDAO()
    updated = dao.update(manager_conn, "P002", {"price": Decimal("21.50"), "stock_warn": 8})
    assert updated is not None
    assert updated["price"] == Decimal("21.50")
    assert updated["stock_warn"] == 8

    with pytest.raises(DAOError) as excinfo:
        dao.update(manager_conn, "P002", {"product_id": "P999"})
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR

    assert dao.update(manager_conn, "P999", {"price": Decimal("1.00")}) is None


@pytest.mark.integration
def test_set_status(manager_conn):
    dao = ProductDAO()
    stopped = dao.set_status(manager_conn, "P003", "停售")
    assert stopped is not None and stopped["status"] == "停售"
    assert dao.list(manager_conn, status="停售").total == 1


@pytest.mark.integration
def test_delete_referenced_product_conflicts(manager_conn):
    with pytest.raises(DAOError) as excinfo:
        ProductDAO().delete(manager_conn, "P001")
    assert excinfo.value.code == ErrorCode.CONFLICT_FOREIGN_KEY


@pytest.mark.integration
def test_delete_unreferenced_product(manager_conn):
    dao = ProductDAO()
    product = dao.create(
        manager_conn,
        product_name="待删除商品",
        category=None,
        price=Decimal("1.00"),
    )
    assert dao.delete(manager_conn, product["product_id"]) is True
    assert dao.get(manager_conn, product["product_id"]) is None


@pytest.mark.integration
def test_list_categories(clerk_conn):
    categories = ProductDAO().list_categories(clerk_conn)
    assert len(categories) == 3
    assert len(categories) == len(set(categories))
    assert all(category for category in categories)


@pytest.mark.integration
def test_clerk_cannot_create_product(clerk_conn):
    with pytest.raises(DAOError) as excinfo:
        ProductDAO().create(
            clerk_conn,
            product_name="店员越权商品",
            category=None,
            price=Decimal("1.00"),
        )
    assert excinfo.value.code == ErrorCode.FORBIDDEN
