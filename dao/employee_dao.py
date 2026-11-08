"""Employee and login-credential data access."""

from __future__ import annotations

from typing import Any

from pyodbc import Connection

from .utils import (
    cursor_scope,
    dao_errors,
    ensure_text,
    row_to_dict,
    rows_to_dicts,
)

EMPLOYEE_COLUMNS = "employee_id, employee_name, role, phone, hire_date"


class EmployeeDAO:
    @dao_errors
    def get_credentials(
        self, conn: Connection, login_name: str
    ) -> dict[str, Any] | None:
        login_name = ensure_text(login_name, "登录名", max_length=30)  # type: ignore[assignment]
        with cursor_scope(conn) as cursor:
            cursor.execute(
                """
                SELECT employee_id, employee_name, role, login_name,
                       password_hash, is_active
                FROM dbo.v_employee_login
                WHERE login_name = ?;
                """,
                [login_name],
            )
            return row_to_dict(cursor)

    @dao_errors
    def get(self, conn: Connection, employee_id: str) -> dict[str, Any] | None:
        employee_id = ensure_text(employee_id, "员工编号", max_length=8)  # type: ignore[assignment]
        with cursor_scope(conn) as cursor:
            cursor.execute(
                f"SELECT {EMPLOYEE_COLUMNS} FROM dbo.Employee WHERE employee_id = ?;",
                [employee_id],
            )
            return row_to_dict(cursor)

    @dao_errors
    def list(self, conn: Connection) -> list[dict[str, Any]]:
        with cursor_scope(conn) as cursor:
            cursor.execute(
                f"SELECT {EMPLOYEE_COLUMNS} FROM dbo.Employee ORDER BY employee_id;"
            )
            return rows_to_dicts(cursor)
