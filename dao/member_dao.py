"""Member data access."""

from __future__ import annotations

from typing import Any

from pyodbc import Connection

from .errors import DAOError, ErrorCode
from .ids import next_id
from .models import Page
from .utils import (
    cursor_scope,
    dao_errors,
    ensure_int,
    ensure_text,
    like_pattern,
    require_transaction,
    row_to_dict,
    rows_to_dicts,
    validate_page,
)

MEMBER_COLUMNS = "member_id, member_name, phone, points, join_date"
UPDATABLE = ("member_name", "phone", "points")


class MemberDAO:
    @dao_errors
    def search(
        self,
        conn: Connection,
        *,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page:
        page, page_size = validate_page(page, page_size)

        where: list[str] = []
        params: list[Any] = []

        keyword = ensure_text(keyword, "关键字", max_length=50, required=False)
        if keyword:
            pattern = like_pattern(keyword)
            where.append(
                "(member_id LIKE ? ESCAPE '\\' OR member_name LIKE ? ESCAPE '\\' "
                "OR phone LIKE ? ESCAPE '\\')"
            )
            params.extend([pattern, pattern, pattern])

        clause = f"WHERE {' AND '.join(where)}" if where else ""

        with cursor_scope(conn) as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM dbo.Member {clause};", params)
            total = int(cursor.fetchone()[0])

            cursor.execute(
                f"""
                SELECT {MEMBER_COLUMNS}
                FROM dbo.Member
                {clause}
                ORDER BY member_id
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;
                """,
                [*params, (page - 1) * page_size, page_size],
            )
            items = rows_to_dicts(cursor)

        return Page(items=items, total=total, page=page, page_size=page_size)

    @dao_errors
    def get(self, conn: Connection, member_id: str) -> dict[str, Any] | None:
        member_id = ensure_text(member_id, "会员编号", max_length=8)  # type: ignore[assignment]
        with cursor_scope(conn) as cursor:
            cursor.execute(
                f"SELECT {MEMBER_COLUMNS} FROM dbo.Member WHERE member_id = ?;",
                [member_id],
            )
            return row_to_dict(cursor)

    @dao_errors
    def create(
        self,
        conn: Connection,
        *,
        member_name: str,
        phone: str,
        points: int = 0,
    ) -> dict[str, Any]:
        require_transaction(conn)
        member_name = ensure_text(member_name, "会员姓名", max_length=30)  # type: ignore[assignment]
        phone = ensure_text(phone, "手机号", max_length=20)  # type: ignore[assignment]
        points = ensure_int(points, "积分", minimum=0)

        member_id = next_id(conn, "member")
        with cursor_scope(conn) as cursor:
            cursor.execute(
                """
                INSERT INTO dbo.Member (member_id, member_name, phone, points)
                VALUES (?, ?, ?, ?);
                """,
                [member_id, member_name, phone, points],
            )
        created = self.get(conn, member_id)
        if created is None:
            raise DAOError(ErrorCode.INTERNAL_ERROR, "创建会员后无法读取记录")
        return created

    @dao_errors
    def update(
        self,
        conn: Connection,
        member_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any] | None:
        member_id = ensure_text(member_id, "会员编号", max_length=8)  # type: ignore[assignment]
        if not isinstance(changes, dict):
            raise DAOError(ErrorCode.VALIDATION_ERROR, "changes 必须是字典")

        unknown = set(changes) - set(UPDATABLE)
        if unknown:
            raise DAOError(
                ErrorCode.VALIDATION_ERROR,
                f"不允许修改字段：{', '.join(sorted(unknown))}",
                context={"fields": sorted(unknown)},
            )

        assignments: list[str] = []
        params: list[Any] = []

        if "member_name" in changes:
            assignments.append("member_name = ?")
            params.append(
                ensure_text(changes["member_name"], "会员姓名", max_length=30)
            )
        if "phone" in changes:
            assignments.append("phone = ?")
            params.append(ensure_text(changes["phone"], "手机号", max_length=20))
        if "points" in changes:
            assignments.append("points = ?")
            params.append(ensure_int(changes["points"], "积分", minimum=0))

        if not assignments:
            return self.get(conn, member_id)

        params.append(member_id)
        with cursor_scope(conn) as cursor:
            cursor.execute(
                f"UPDATE dbo.Member SET {', '.join(assignments)} WHERE member_id = ?;",
                params,
            )
            if cursor.rowcount == 0:
                return None
        return self.get(conn, member_id)

    @dao_errors
    def add_points(self, conn: Connection, member_id: str, delta: int) -> dict[str, Any] | None:
        member_id = ensure_text(member_id, "会员编号", max_length=8)  # type: ignore[assignment]
        delta = ensure_int(delta, "积分变动")

        with cursor_scope(conn) as cursor:
            cursor.execute(
                """
                UPDATE dbo.Member
                SET points = points + ?
                WHERE member_id = ? AND points + ? >= 0;
                """,
                [delta, member_id, delta],
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "SELECT points FROM dbo.Member WHERE member_id = ?;",
                    [member_id],
                )
                existing = cursor.fetchone()
                if existing is None:
                    return None
                raise DAOError(
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    "积分不足，不能扣减",
                    context={
                        "member_id": member_id,
                        "available": int(existing[0]),
                        "requested": -delta,
                    },
                )
        return self.get(conn, member_id)
