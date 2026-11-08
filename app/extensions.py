"""全局共享的数据库入口（成员B 连接管理）。

DAO 契约约定事务边界归业务层（B），因此这里只维护一个 ``Database`` 单例，
由各 service 通过 ``get_db()`` 获取后调用 ``db.read(...)`` / ``db.transaction(...)``。
"""

from __future__ import annotations

from dao import ConfigError, DAOError, Database, DbConfig, ErrorCode

_db: Database | None = None


def get_db() -> Database:
    """懒加载返回 ``Database`` 单例；未配置 ``.env`` 时给出友好错误。"""
    global _db
    if _db is None:
        try:
            config = DbConfig.from_env()
        except ConfigError as exc:
            raise DAOError(
                ErrorCode.DB_UNAVAILABLE,
                "数据库尚未配置，请先复制 .env.example 为 .env 并填写账号密码",
                detail=str(exc),
            ) from exc
        _db = Database(config)
    return _db


def reset_db() -> None:
    """测试用：清空单例，下次 ``get_db()`` 重新加载配置。"""
    global _db
    _db = None
