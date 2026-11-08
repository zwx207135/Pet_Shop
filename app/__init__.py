"""Flask 应用工厂（成员B）。

分层：页面层（routes）→ 业务层（services）→ 数据访问层 DAO（成员A）。
连接与事务边界在业务层，DAO 不 commit / 不 rollback / 不关闭连接。
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from decimal import Decimal
from logging.handlers import RotatingFileHandler

from flask import Flask

from .config import FlaskConfig
from .errors import register_error_handlers

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")


def _setup_logging() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    logger = logging.getLogger("petcare.web")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        file_handler = RotatingFileHandler(
            os.path.join(LOG_DIR, "app.log"),
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(fmt)
        logger.addHandler(stream_handler)


def create_app() -> Flask:
    _setup_logging()

    app = Flask(__name__)
    app.config.from_object(FlaskConfig)

    register_error_handlers(app)
    _register_template_helpers(app)
    _register_blueprints(app)

    return app


def _register_template_helpers(app: Flask) -> None:
    from .security import current_user

    @app.context_processor
    def inject_user():
        return {"current_user": current_user()}

    @app.template_filter("money")
    def money(value):
        if value is None:
            return "-"
        return f"{Decimal(str(value)):,.2f}"

    @app.template_filter("dt")
    def dt(value):
        if value is None:
            return "-"
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        return str(value)

    @app.template_filter("date")
    def date_fmt(value):
        if value is None:
            return "-"
        if isinstance(value, (date, datetime)):
            return value.strftime("%Y-%m-%d")
        return str(value)


def _register_blueprints(app: Flask) -> None:
    from .routes import (
        auth,
        employees,
        inventory,
        main,
        members,
        orders,
        products,
        reports,
    )

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(products.bp)
    app.register_blueprint(inventory.bp)
    app.register_blueprint(orders.bp)
    app.register_blueprint(members.bp)
    app.register_blueprint(employees.bp)
    app.register_blueprint(reports.bp)
