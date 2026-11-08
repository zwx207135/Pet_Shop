"""生成 app_18_后端日志结构.png：把 result/app_log_sample.txt 以等宽字体渲染后截图。"""

from __future__ import annotations

import html
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

RESULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "result")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def main() -> int:
    txt_path = os.path.join(RESULT, "app_log_sample.txt")
    with open(txt_path, encoding="utf-8") as f:
        txt = f.read()

    body = (
        '<pre style="font:14px/1.5 Consolas,Menlo,monospace; margin:24px; white-space:pre-wrap;">'
        + html.escape(txt)
        + "</pre>"
    )
    doc = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<title>后端日志结构</title></head>'
        '<body style="background:#fff;">' + body + "</body></html>"
    )
    hp = os.path.join(RESULT, "_app_log_sample.html")
    with open(hp, "w", encoding="utf-8") as f:
        f.write(doc)

    opts = Options()
    opts.binary_location = CHROME
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--force-device-scale-factor=1")
    d = webdriver.Chrome(options=opts)
    d.implicitly_wait = 5
    d.get("file:///" + hp.replace("\\", "/"))
    time.sleep(0.6)
    d.save_screenshot(os.path.join(RESULT, "app_18_后端日志结构.png"))
    d.quit()
    os.remove(hp)
    print("saved app_18_后端日志结构.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
