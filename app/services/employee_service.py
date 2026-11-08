"""员工业务（成员B）。店长专用：读取 Employee 基表。"""

from __future__ import annotations

from dao import EmployeeDAO

from app.extensions import get_db


def list_employees() -> list[dict]:
    # 只有店长角色能走到这里；店员连接会因数据库权限失败（双重防线）。
    with get_db().read("manager") as conn:
        return EmployeeDAO().list(conn)
