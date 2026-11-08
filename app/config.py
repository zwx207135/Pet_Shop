"""Flask 应用配置（成员B）。

数据库连接信息不在这里维护，由 ``dao.DbConfig`` 从 ``.env`` 读取；
这里只放 Flask 自身的配置项。
"""

from __future__ import annotations

import os


class FlaskConfig:
    """Flask 配置对象。

    会话密钥仅用于课程演示，生产环境请通过 ``FLASK_SECRET_KEY`` 环境变量注入。
    """

    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "petcare-dev-secret-change-me")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    MAX_CONTENT_LENGTH = 1024 * 1024  # 1 MB，防止超大表单
