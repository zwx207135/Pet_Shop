"""会员业务（成员B）。"""

from __future__ import annotations

from dao import DAOError, ErrorCode, MemberDAO

from app.extensions import get_db
from app.security import db_role
from app.services.validation import parse_int


def search_members(*, keyword=None, page=1, page_size=20):
    with get_db().read(db_role()) as conn:
        return MemberDAO().search(conn, keyword=keyword, page=page, page_size=page_size)


def list_members_for_select(*, keyword=None) -> list[dict]:
    """订单页会员下拉：最多取 100 条。"""
    with get_db().read(db_role()) as conn:
        return MemberDAO().search(conn, keyword=keyword, page=1, page_size=100).items


def get_member(member_id: str):
    with get_db().read(db_role()) as conn:
        return MemberDAO().get(conn, member_id)


def create_member(form: dict) -> dict:
    with get_db().transaction(db_role()) as conn:
        return MemberDAO().create(
            conn,
            member_name=form.get("member_name", ""),
            phone=form.get("phone", ""),
            points=parse_int(form.get("points"), "积分", default=0, minimum=0),
        )


def update_member(member_id: str, form: dict) -> dict:
    changes = {
        "member_name": form.get("member_name", ""),
        "phone": form.get("phone", ""),
        "points": parse_int(form.get("points"), "积分", default=0, minimum=0),
    }
    with get_db().transaction(db_role()) as conn:
        updated = MemberDAO().update(conn, member_id, changes)
    if updated is None:
        raise DAOError(ErrorCode.NOT_FOUND, "会员不存在")
    return updated


def add_points(member_id: str, delta: int) -> dict:
    with get_db().transaction(db_role()) as conn:
        updated = MemberDAO().add_points(conn, member_id, delta)
    if updated is None:
        raise DAOError(ErrorCode.NOT_FOUND, "会员不存在")
    return updated
