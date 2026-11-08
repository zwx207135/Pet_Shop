"""表单校验与业务规则在业务层的判断/传播（成员B，DB 无关）。

覆盖：
- ``parse_int`` / ``parse_decimal``：非整数、负数、超长、空值 -> VALIDATION_ERROR；
- 表单层 ``_parse_items``：跳过空商品、数量校验、空明细拦截；
- ``order_service.create_order``：把明细转换为 ``OrderItemInput`` 原样转发，
  库存不足 / 停售商品等业务规则（由 DAO 判定）的 ``DAOError`` 原样传播，业务层不吞异常。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from flask import Flask, session

from dao import DAOError, ErrorCode, OrderItemInput

from app.routes.orders import _parse_items
from app.services import order_service
from app.services.validation import parse_decimal, parse_int


@pytest.fixture
def app():
    application = Flask(__name__)
    application.config["SECRET_KEY"] = "test"
    application.config["TESTING"] = True
    return application


# ---------- parse_int / parse_decimal ----------

def test_parse_int_ok():
    assert parse_int("3", "数量") == 3


def test_parse_int_non_int_raises_validation():
    with pytest.raises(DAOError) as ei:
        parse_int("abc", "数量")
    assert ei.value.code == "VALIDATION_ERROR"


def test_parse_int_negative_raises_validation():
    with pytest.raises(DAOError) as ei:
        parse_int("-1", "数量", minimum=1)
    assert ei.value.code == "VALIDATION_ERROR"


def test_parse_int_empty_raises_validation():
    with pytest.raises(DAOError) as ei:
        parse_int("", "数量")
    assert ei.value.code == "VALIDATION_ERROR"


def test_parse_decimal_ok():
    from decimal import Decimal

    assert parse_decimal("39.90", "价格") == Decimal("39.90")


def test_parse_decimal_non_numeric_raises_validation():
    with pytest.raises(DAOError) as ei:
        parse_decimal("abc", "金额")
    assert ei.value.code == "VALIDATION_ERROR"


# ---------- _parse_items（表单层）----------

def test_parse_items_skips_empty_and_parses_quantity():
    items = _parse_items(["P001", "", "P002"], ["2", "3", "1"])
    assert items == [("P001", 2), ("P002", 1)]


def test_parse_items_non_int_quantity_raises():
    with pytest.raises(DAOError) as ei:
        _parse_items(["P001"], ["abc"])
    assert ei.value.code == "VALIDATION_ERROR"


def test_parse_items_negative_quantity_raises():
    with pytest.raises(DAOError) as ei:
        _parse_items(["P001"], ["-5"])
    assert ei.value.code == "VALIDATION_ERROR"


def test_parse_items_all_empty_raises():
    with pytest.raises(DAOError) as ei:
        _parse_items(["", ""], ["", ""])
    assert ei.value.code == "VALIDATION_ERROR"


# ---------- order_service.create_order（业务规则传播）----------

@pytest.fixture
def fake_order(monkeypatch):
    from tests._app_utils import FakeDB

    dao = MagicMock()
    monkeypatch.setattr(order_service, "get_db", lambda: FakeDB())
    monkeypatch.setattr(order_service, "OrderDAO", lambda: dao)
    return dao


def test_create_order_forwards_order_item_inputs(app, fake_order):
    fake_order.create_with_details.return_value = {"order_id": "O001"}
    with app.test_request_context():
        session["employee_id"] = "E002"
        session["role"] = "店员"
        order_service.create_order(
            member_id="M001",
            pay_method="微信",
            items=[("P001", 2), ("P002", 1), ("P002", 2)],
        )
    _, kwargs = fake_order.create_with_details.call_args
    items = kwargs["items"]
    assert len(items) == 3  # 原始明细原样传入，重复合并由 DAO 完成
    assert all(isinstance(i, OrderItemInput) for i in items)
    assert [(i.product_id, i.quantity) for i in items] == [("P001", 2), ("P002", 1), ("P002", 2)]
    assert kwargs["pay_method"] == "微信"
    assert kwargs["employee_id"] == "E002"


def test_create_order_propagates_insufficient_stock(app, fake_order):
    fake_order.create_with_details.side_effect = DAOError(
        ErrorCode.BUSINESS_RULE_VIOLATION,
        "库存不足",
        context={"available": 2, "requested": 3},
    )
    with app.test_request_context():
        session["employee_id"] = "E002"
        session["role"] = "店员"
        with pytest.raises(DAOError) as ei:
            order_service.create_order(member_id=None, pay_method="现金", items=[("P001", 3)])
        assert ei.value.code == "BUSINESS_RULE_VIOLATION"
        assert "库存不足" in ei.value.message


def test_create_order_propagates_stopped_product(app, fake_order):
    fake_order.create_with_details.side_effect = DAOError(
        ErrorCode.BUSINESS_RULE_VIOLATION,
        "商品已停售",
        context={"product_id": "P001", "status": "停售"},
    )
    with app.test_request_context():
        session["employee_id"] = "E002"
        session["role"] = "店员"
        with pytest.raises(DAOError) as ei:
            order_service.create_order(member_id=None, pay_method="现金", items=[("P001", 1)])
        assert ei.value.code == "BUSINESS_RULE_VIOLATION"
        assert "停售" in ei.value.message
