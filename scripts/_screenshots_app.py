"""Task B: 用真实浏览器（Selenium + 本机 Chrome 无头模式）对运行中的 Flask 应用
逐页截图，保存到 result/app_*.png。所有截图均为真实页面渲染结果。
"""

from __future__ import annotations

import os
import time

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE = "http://127.0.0.1:5000"
RESULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "result")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def new_driver() -> webdriver.Chrome:
    opts = Options()
    opts.binary_location = CHROME
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--force-device-scale-factor=1")
    opts.add_argument("--hide-scrollbars")
    d = webdriver.Chrome(options=opts)
    d.implicitly_wait(5)
    return d


def shot(d: webdriver.Chrome, name: str) -> None:
    path = os.path.join(RESULT, name)
    d.save_screenshot(path)
    print(f"  saved {name}")


def login(d: webdriver.Chrome, user: str, password: str) -> None:
    d.get(BASE + "/login")
    d.find_element(By.NAME, "login_name").send_keys(user)
    d.find_element(By.NAME, "password").send_keys(password)
    d.find_element(By.CSS_SELECTOR, "button[type=submit], input[type=submit]").click()
    WebDriverWait(d, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "main.container"))
    )
    time.sleep(0.4)


def logout(d: webdriver.Chrome) -> None:
    d.execute_script("document.querySelector('form[action*=\"/logout\"]').submit();")
    WebDriverWait(d, 10).until(lambda x: x.current_url.endswith("/login"))
    time.sleep(0.3)


def post_show_html(d: webdriver.Chrome, body: str) -> dict:
    """用同源 fetch 提交表单，把服务端返回的 HTML 渲染到当前页面（保持 CSS）。"""
    script = """
    const done = arguments[arguments.length - 1];
    (async () => {
      const resp = await fetch('/orders/new', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: arguments[0],
        redirect: 'follow'
      });
      const html = await resp.text();
      document.open();
      document.write(html);
      document.close();
      done({status: resp.status, url: resp.url});
    })();
    """
    result = d.execute_async_script(script, body)
    time.sleep(0.5)
    return result


def post_order(d: webdriver.Chrome, body: str) -> dict:
    """提交订单并返回最终跳转地址（订单详情页）。"""
    script = """
    const done = arguments[arguments.length - 1];
    (async () => {
      const resp = await fetch('/orders/new', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: arguments[0],
        redirect: 'follow'
      });
      done({status: resp.status, url: resp.url});
    })();
    """
    return d.execute_async_script(script, body)


def scroll_to(d: webdriver.Chrome, text: str) -> None:
    el = d.find_element(By.XPATH, f"//h3[contains(text(),'{text}')]")
    d.execute_script("arguments[0].scrollIntoView({block:'start', behavior:'instant'});", el)
    time.sleep(0.3)


def hstack(imgs: list[str], out: str) -> None:
    images = [Image.open(os.path.join(RESULT, i)) for i in imgs]
    w = sum(i.width for i in images)
    h = max(i.height for i in images)
    canvas = Image.new("RGB", (w, h), "white")
    x = 0
    for im in images:
        canvas.paste(im, (x, 0))
        x += im.width
    canvas.save(os.path.join(RESULT, out))
    print(f"  stitched {out}")


def main() -> int:
    # ---------------- 未登录 ---------------
    g = new_driver()
    g.get(BASE + "/login")
    time.sleep(0.5)
    shot(g, "app_01_登录页.png")

    g.get(BASE + "/orders")
    time.sleep(0.6)  # 未登录访问受保护页 -> 302 到 /login?next=/orders
    shot(g, "app_14_未登录访问重定向登录.png")
    g.quit()

    # ---------------- 店员 ---------------
    c = new_driver()
    login(c, "clerk", "Clerk@123")
    shot(c, "app_02_店员工作台.png")

    c.get(BASE + "/products")
    time.sleep(0.5)
    shot(c, "app_04_商品列表.png")

    c.get(BASE + "/orders/new")
    time.sleep(0.5)
    shot(c, "app_05_开单表单.png")

    # 开单（重复商品合并演示：P001×2 + P002×3）
    r = post_order(c, "member_id=M001&pay_method=微信&product_id=P001&quantity=2&product_id=P002&quantity=3")
    print(f"  order POST status={r['status']} url={r['url']}")
    c.get(r["url"])
    time.sleep(0.5)
    shot(c, "app_06_开单成功_订单详情.png")

    c.get(BASE + "/inventory")
    time.sleep(0.5)
    shot(c, "tmp_inventory.png")
    c.get(BASE + "/inventory/logs")
    time.sleep(0.5)
    shot(c, "tmp_logs.png")
    hstack(["tmp_inventory.png", "tmp_logs.png"], "app_07_库存与流水.png")

    c.get(BASE + "/members")
    time.sleep(0.5)
    shot(c, "app_09_会员管理.png")

    # 店员越权访问店长专属路由 -> 302 重定向首页 + 友好提示
    c.get(BASE + "/employees")
    time.sleep(0.6)
    shot(c, "app_13_店员越权访问403.png")

    # 参数错误（数量非整数，走服务端校验）
    c.get(BASE + "/orders/new")
    time.sleep(0.3)
    post_show_html(c, "member_id=&pay_method=现金&product_id=P001&quantity=abc")
    shot(c, "app_15_参数错误提示.png")

    # 库存不足 -> 整单回滚
    c.get(BASE + "/orders/new")
    time.sleep(0.3)
    post_show_html(c, "member_id=&pay_method=现金&product_id=P001&quantity=99999")
    shot(c, "app_16_库存不足整单回滚提示.png")

    # 停售商品下单被拒
    c.get(BASE + "/orders/new")
    time.sleep(0.3)
    post_show_html(c, "member_id=&pay_method=现金&product_id=P0001003&quantity=1")
    shot(c, "app_17_停售商品下单被拒.png")
    c.quit()

    # ---------------- 店长 ---------------
    m = new_driver()
    login(m, "manager", "Manager@123")
    shot(m, "app_03_店长工作台.png")

    # 补货入库前后对比（用低库存商品 P0001004）
    m.get(BASE + "/inventory/P0001004/adjust")
    time.sleep(0.5)
    shot(m, "tmp_before.png")
    m.find_element(By.NAME, "change_qty").send_keys("20")
    m.find_element(By.NAME, "remark").send_keys("截图演示补货")
    m.find_element(By.XPATH, "//button[contains(text(),'确认入库')]").click()
    WebDriverWait(m, 10).until(lambda x: x.current_url.rstrip("/").endswith("/inventory"))
    time.sleep(0.6)
    shot(m, "tmp_after.png")
    hstack(["tmp_before.png", "tmp_after.png"], "app_08_补货入库前后对比.png")

    # 经营报表三个板块：整页截图后按 h3 坐标裁剪，确保三个板块各自独立
    m.get(BASE + "/reports")
    time.sleep(0.5)
    info = m.execute_script(
        """
        const hs = Array.from(document.querySelectorAll('h3'));
        const scrollY = window.scrollY;
        const marks = {};
        for (const h of hs) {
          marks[h.textContent.trim()] = h.getBoundingClientRect().top + scrollY;
        }
        return {marks: marks, totalH: document.body.scrollHeight};
        """
    )
    full_h = info["totalH"]
    m.set_window_size(1280, full_h + 60)
    time.sleep(0.4)
    full = os.path.join(RESULT, "tmp_reports_full.png")
    m.save_screenshot(full)
    m.quit()

    marks = info["marks"]
    y_sales = next(v for k, v in marks.items() if "商品销售" in k)
    y_stock = next(v for k, v in marks.items() if "库存状态" in k)
    y_consume = next(v for k, v in marks.items() if "会员消费" in k)
    full_im = Image.open(full)
    w, _h = full_im.size
    full_im.crop((0, max(0, y_sales - 10), w, y_stock)).save(os.path.join(RESULT, "app_10_报表_商品销售.png"))
    full_im.crop((0, y_stock, w, y_consume)).save(os.path.join(RESULT, "app_11_报表_库存状态.png"))
    full_im.crop((0, y_consume, w, _h)).save(os.path.join(RESULT, "app_12_报表_会员消费.png"))
    os.remove(full)
    print("  cropped app_10/11/12 报表板块")

    # 清理临时图
    for t in ("tmp_inventory.png", "tmp_logs.png", "tmp_before.png", "tmp_after.png"):
        p = os.path.join(RESULT, t)
        if os.path.exists(p):
            os.remove(p)

    print("\n=== SCREENSHOTS DONE ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
