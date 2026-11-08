import pytest

from dao.errors import ErrorCode, TransactionStateError
from dao.inventory_dao import InventoryDAO


@pytest.mark.integration
def test_ping_all_roles(db):
    assert db.ping("clerk") is True
    assert db.ping("manager") is True
    assert db.ping("auth") is True


@pytest.mark.integration
def test_nested_transaction_is_rejected(db):
    with db.transaction("clerk"):
        with pytest.raises(TransactionStateError) as excinfo:
            with db.transaction("clerk"):
                pass
    assert excinfo.value.code == ErrorCode.TRANSACTION_FAILED


@pytest.mark.integration
def test_transaction_rolls_back_on_exception(db):
    with pytest.raises(RuntimeError):
        with db.transaction("clerk") as conn:
            InventoryDAO().adjust(
                conn, "P003", change_qty=1, change_type="入库", remark="pytest-rollback"
            )
            assert InventoryDAO().get(conn, "P003")["quantity"] == 16
            raise RuntimeError("force rollback")

    with db.read("clerk") as conn:
        assert InventoryDAO().get(conn, "P003")["quantity"] == 15


@pytest.mark.integration
def test_transaction_commits_on_success(db, purge_logs):
    try:
        with db.transaction("clerk") as conn:
            InventoryDAO().adjust(
                conn, "P003", change_qty=1, change_type="入库", remark="pytest-commit-up"
            )

        with db.read("clerk") as conn:
            assert InventoryDAO().get(conn, "P003")["quantity"] == 16

        with db.transaction("clerk") as conn:
            InventoryDAO().adjust(
                conn, "P003", change_qty=-1, change_type="销售", remark="pytest-commit-down"
            )

        with db.read("clerk") as conn:
            assert InventoryDAO().get(conn, "P003")["quantity"] == 15
    finally:
        purge_logs("pytest-commit-up", "pytest-commit-down")
