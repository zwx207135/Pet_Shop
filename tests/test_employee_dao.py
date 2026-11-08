import pyodbc
import pytest

from dao.employee_dao import EmployeeDAO
from dao.errors import DAOError, ErrorCode, translate_pyodbc_error


@pytest.mark.integration
def test_get_credentials(auth_conn):
    dao = EmployeeDAO()
    clerk = dao.get_credentials(auth_conn, "clerk")
    assert clerk is not None
    assert clerk["employee_id"] == "E002"
    assert clerk["role"] == "店员"
    assert clerk["login_name"] == "clerk"
    assert clerk["is_active"] is True
    assert clerk["password_hash"].startswith("scrypt:")

    manager = dao.get_credentials(auth_conn, "manager")
    assert manager is not None
    assert manager["employee_id"] == "E001"
    assert manager["role"] == "店长"

    assert dao.get_credentials(auth_conn, "nobody") is None


@pytest.mark.integration
def test_manager_can_list_employees(manager_conn):
    employees = EmployeeDAO().list(manager_conn)
    assert [employee["employee_id"] for employee in employees] == ["E001", "E002"]
    assert EmployeeDAO().get(manager_conn, "E001")["role"] == "店长"


@pytest.mark.integration
def test_clerk_cannot_read_employees(clerk_conn):
    with pytest.raises(DAOError) as excinfo:
        EmployeeDAO().list(clerk_conn)
    assert excinfo.value.code == ErrorCode.FORBIDDEN


@pytest.mark.integration
def test_auth_account_has_only_the_login_view(auth_conn):
    with pytest.raises(pyodbc.Error) as excinfo:
        auth_conn.cursor().execute("SELECT TOP 1 product_id FROM dbo.Product;").fetchone()
    assert translate_pyodbc_error(excinfo.value).code == ErrorCode.FORBIDDEN
