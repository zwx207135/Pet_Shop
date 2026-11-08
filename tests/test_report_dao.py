from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from dao.errors import DAOError, ErrorCode
from dao.report_dao import ReportDAO


@pytest.mark.integration
def test_product_sales(clerk_conn):
    rows = ReportDAO().product_sales(clerk_conn)
    assert [row["product_id"] for row in rows] == ["P001", "P002", "P003"]
    assert rows[0]["sold_qty"] == 1
    assert rows[0]["sales_amount"] == Decimal("128.00")
    assert rows[2]["sold_qty"] == 0
    assert rows[2]["sales_amount"] == Decimal("0.00")


@pytest.mark.integration
def test_product_sales_date_filter(clerk_conn):
    future = datetime.now() + timedelta(days=30)
    rows = ReportDAO().product_sales(clerk_conn, start=future)
    assert len(rows) == 3
    assert all(row["sold_qty"] == 0 for row in rows)
    assert all(row["sales_amount"] == Decimal("0.00") for row in rows)

    assert len(ReportDAO().product_sales(clerk_conn, limit=2)) == 2


@pytest.mark.integration
def test_inventory_status(clerk_conn):
    dao = ReportDAO()
    rows = dao.inventory_status(clerk_conn)
    assert [row["product_id"] for row in rows] == ["P001", "P002", "P003"]
    assert all(row["stock_status"] == "正常" for row in rows)
    assert dao.inventory_status(clerk_conn, low_stock_only=True) == []


@pytest.mark.integration
def test_member_consumption(clerk_conn):
    dao = ReportDAO()
    rows = dao.member_consumption(clerk_conn)
    assert [row["member_id"] for row in rows] == ["M001", "M002"]
    assert rows[0]["order_count"] == 1
    assert rows[0]["total_spent"] == Decimal("128.00")
    assert rows[1]["order_count"] == 0
    assert rows[1]["total_spent"] == Decimal("0.00")

    only_m001 = dao.member_consumption(clerk_conn, member_id="M001")
    assert len(only_m001) == 1
    assert len(dao.member_consumption(clerk_conn, limit=1)) == 1


@pytest.mark.integration
def test_invalid_ranges(clerk_conn):
    now = datetime.now()
    with pytest.raises(DAOError) as excinfo:
        ReportDAO().product_sales(clerk_conn, start=now, end=now - timedelta(days=1))
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR

    with pytest.raises(DAOError) as excinfo:
        ReportDAO().member_consumption(clerk_conn, limit=0)
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR
