"""PetCare Web 应用启动入口（成员B）。

启动方式（项目根目录）：
    python run.py
或
    flask --app run run
"""

from __future__ import annotations

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
