"""Render the PetCare v1.0 ER diagram to SVG and PNG.

Usage:
    py docs/er/render_er.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parent
FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"
FONT = FontProperties(fname=FONT_PATH)
FONT_BOLD = FontProperties(fname=FONT_PATH, weight="bold")

INK = "#1F2937"
BLUE = "#2F5597"
LIGHT = "#F5F8FD"
GREY = "#6B7280"

ENTITIES = {
    "Employee": {
        "label": "员工",
        "x": 40,
        "y": 40,
        "fields": [
            ("employee_id", "PK"),
            ("employee_name", ""),
            ("role", ""),
            ("phone", "UK"),
            ("hire_date", ""),
            ("login_name", "UK"),
            ("password_hash", ""),
            ("is_active", ""),
        ],
    },
    "Member": {
        "label": "会员",
        "x": 40,
        "y": 320,
        "fields": [
            ("member_id", "PK"),
            ("member_name", ""),
            ("phone", "UK"),
            ("points", ""),
            ("join_date", ""),
        ],
    },
    "Orders": {
        "label": "订单",
        "x": 430,
        "y": 40,
        "fields": [
            ("order_id", "PK"),
            ("member_id", "FK"),
            ("employee_id", "FK"),
            ("order_type", ""),
            ("order_time", ""),
            ("total_amount", ""),
            ("pay_method", ""),
            ("order_status", ""),
        ],
    },
    "OrderDetail": {
        "label": "订单明细",
        "x": 860,
        "y": 40,
        "fields": [
            ("detail_id", "PK"),
            ("order_id", "FK"),
            ("product_id", "FK"),
            ("quantity", ""),
            ("unit_price", ""),
            ("subtotal", "计算列"),
        ],
    },
    "Product": {
        "label": "商品",
        "x": 1260,
        "y": 40,
        "fields": [
            ("product_id", "PK"),
            ("product_name", ""),
            ("category", ""),
            ("price", ""),
            ("stock_warn", ""),
            ("status", ""),
        ],
    },
    "Inventory": {
        "label": "库存",
        "x": 1260,
        "y": 340,
        "fields": [
            ("inventory_id", "PK"),
            ("product_id", "FK, UK"),
            ("quantity", ""),
            ("update_time", ""),
        ],
    },
    "InventoryLog": {
        "label": "库存变动记录",
        "x": 1260,
        "y": 620,
        "fields": [
            ("log_id", "PK"),
            ("product_id", "FK"),
            ("change_type", ""),
            ("change_qty", ""),
            ("change_time", ""),
            ("remark", ""),
        ],
    },
    "PetService": {
        "label": "服务项目",
        "x": 40,
        "y": 620,
        "fields": [
            ("service_id", "PK"),
            ("service_name", ""),
            ("price", ""),
            ("duration_min", ""),
            ("status", ""),
        ],
    },
    "ServiceAppointment": {
        "label": "服务预约",
        "x": 430,
        "y": 620,
        "fields": [
            ("appointment_id", "PK"),
            ("member_id", "FK"),
            ("service_id", "FK"),
            ("employee_id", "FK"),
            ("appoint_time", ""),
            ("status", ""),
            ("remark", ""),
        ],
    },
}

WIDTH = 280
TITLE_H = 34
LINE_H = 22
PAD = 20


def box_height(entity: dict) -> int:
    return TITLE_H + LINE_H * len(entity["fields"]) + PAD


def draw_entity(ax: plt.Axes, name: str, entity: dict) -> None:
    x, y = entity["x"], entity["y"]
    h = box_height(entity)
    ax.add_patch(
        Rectangle(
            (x, y),
            WIDTH,
            h,
            facecolor=LIGHT,
            edgecolor=BLUE,
            linewidth=1.4,
            zorder=2,
        )
    )
    ax.add_patch(
        Rectangle(
            (x, y),
            WIDTH,
            TITLE_H,
            facecolor=BLUE,
            edgecolor=BLUE,
            linewidth=1.4,
            zorder=3,
        )
    )
    ax.text(
        x + 12,
        y + TITLE_H / 2,
        f"{name}  {entity['label']}",
        color="white",
        fontproperties=FONT_BOLD,
        fontsize=12,
        va="center",
        zorder=4,
    )
    for index, (field, marker) in enumerate(entity["fields"]):
        line_y = y + TITLE_H + 16 + index * LINE_H
        weight = "bold" if marker.startswith("PK") else "normal"
        props = FontProperties(fname=FONT_PATH, weight=weight)
        ax.text(
            x + 12,
            line_y,
            field,
            color=INK,
            fontproperties=props,
            fontsize=9.5,
            va="center",
            zorder=4,
        )
        if marker:
            ax.text(
                x + WIDTH - 12,
                line_y,
                marker,
                color=GREY,
                fontproperties=FONT,
                fontsize=8,
                ha="right",
                va="center",
                zorder=4,
            )


def polyline(ax: plt.Axes, points: list[tuple[float, float]]) -> None:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    ax.plot(xs, ys, color=BLUE, linewidth=1.3, zorder=1, solid_capstyle="round")


def many_mark(ax: plt.Axes, x: float, y: float, direction: str) -> None:
    spread = 9
    length = 16
    if direction == "right":
        points = [(x - length, y + spread), (x, y), (x - length, y - spread)]
    elif direction == "left":
        points = [(x + length, y + spread), (x, y), (x + length, y - spread)]
    elif direction == "up":
        points = [(x + spread, y + length), (x, y), (x - spread, y + length)]
    else:
        points = [(x + spread, y - length), (x, y), (x - spread, y - length)]
    for start in points[::2]:
        ax.plot(
            [start[0], points[1][0]],
            [start[1], points[1][1]],
            color=BLUE,
            linewidth=1.2,
            zorder=1,
        )


def one_mark(ax: plt.Axes, x: float, y: float, direction: str) -> None:
    half = 8
    if direction in {"right", "left"}:
        ax.plot([x, x], [y - half, y + half], color=BLUE, linewidth=1.2, zorder=1)
    else:
        ax.plot([x - half, x + half], [y, y], color=BLUE, linewidth=1.2, zorder=1)


def label(ax: plt.Axes, x: float, y: float, text: str, *, ha: str = "center") -> None:
    ax.text(
        x,
        y,
        text,
        color=INK,
        fontproperties=FONT,
        fontsize=9,
        ha=ha,
        va="center",
        bbox={"boxstyle": "round,pad=0.15", "facecolor": "white", "edgecolor": "none"},
        zorder=5,
    )


def rel_label(ax: plt.Axes, x: float, y: float, text: str, *, ha: str = "center") -> None:
    ax.text(
        x,
        y,
        text,
        color=GREY,
        fontproperties=FontProperties(fname=FONT_PATH, style="italic"),
        fontsize=8.5,
        ha=ha,
        va="center",
        bbox={"boxstyle": "round,pad=0.1", "facecolor": "white", "edgecolor": "none"},
        zorder=5,
    )


def draw_relationships(ax: plt.Axes) -> None:
    # Employee 1 -- 0..N Orders
    polyline(ax, [(320, 150), (430, 150)])
    one_mark(ax, 368, 150, "right")
    many_mark(ax, 430, 150, "right")
    label(ax, 338, 136, "1")
    label(ax, 412, 136, "0..N")
    rel_label(ax, 375, 165, "经办")

    # Member 0..1 -- 0..N Orders
    polyline(ax, [(320, 400), (375, 400), (375, 255), (430, 255)])
    one_mark(ax, 320, 400, "right")
    many_mark(ax, 430, 255, "right")
    label(ax, 338, 386, "0..1")
    label(ax, 410, 241, "0..N")
    rel_label(ax, 402, 282, "下单")

    # Orders 1 -- 1..N OrderDetail
    polyline(ax, [(710, 170), (860, 170)])
    one_mark(ax, 790, 170, "right")
    many_mark(ax, 860, 170, "right")
    label(ax, 735, 156, "1")
    label(ax, 842, 156, "1..N")
    rel_label(ax, 785, 185, "包含")

    # OrderDetail 0..N -- 1 Product
    polyline(ax, [(1140, 140), (1260, 140)])
    many_mark(ax, 1140, 140, "left")
    one_mark(ax, 1210, 140, "right")
    label(ax, 1155, 126, "0..N")
    label(ax, 1245, 126, "1")
    rel_label(ax, 1200, 155, "被购买")

    # Product 1 -- 0..1 Inventory
    polyline(ax, [(1400, 218), (1400, 340)])
    one_mark(ax, 1400, 270, "up")
    one_mark(ax, 1400, 326, "up")
    label(ax, 1414, 242, "1")
    label(ax, 1414, 320, "0..1")
    rel_label(ax, 1388, 280, "对应", ha="right")

    # Product 1 -- 0..N InventoryLog
    polyline(ax, [(1260, 100), (1195, 100), (1195, 700), (1260, 700)])
    one_mark(ax, 1260, 100, "left")
    many_mark(ax, 1260, 700, "left")
    label(ax, 1246, 86, "1")
    label(ax, 1244, 686, "0..N")
    rel_label(ax, 1180, 400, "产生", ha="right")

    # Employee 0..1 -- 0..N ServiceAppointment
    polyline(ax, [(40, 240), (18, 240), (18, 580), (520, 580), (520, 620)])
    one_mark(ax, 40, 240, "right")
    many_mark(ax, 520, 620, "down")
    label(ax, 34, 226, "0..1")
    label(ax, 506, 606, "0..N")
    rel_label(ax, 350, 566, "负责")

    # Member 0..1 -- 0..N ServiceAppointment
    polyline(ax, [(180, 476), (180, 595), (620, 595), (620, 620)])
    one_mark(ax, 180, 476, "down")
    many_mark(ax, 620, 620, "down")
    label(ax, 194, 490, "0..1")
    label(ax, 634, 606, "0..N")
    rel_label(ax, 300, 609, "预约")

    # PetService 1 -- 1..N ServiceAppointment
    polyline(ax, [(300, 700), (430, 700)])
    one_mark(ax, 360, 700, "right")
    many_mark(ax, 430, 700, "right")
    label(ax, 322, 686, "1")
    label(ax, 412, 686, "0..N")
    rel_label(ax, 365, 715, "被预约")


def draw_legend(ax: plt.Axes) -> None:
    ax.add_patch(
        Rectangle(
            (40, 900),
            700,
            220,
            facecolor="white",
            edgecolor="#D1D5DB",
            linewidth=1,
        )
    )
    ax.text(
        60,
        925,
        "图例",
        color=BLUE,
        fontproperties=FONT_BOLD,
        fontsize=12,
        va="center",
    )
    lines = [
        "PK 主码    FK 外码    UK 唯一约束    计算列 由数据库计算",
        "矩形：实体；连线：联系；连线两端文字：最小..最大基数",
        "1      恰好一个          0..1   可选一个",
        "1..N   一到多个          0..N   零到多个",
    ]
    for index, text in enumerate(lines):
        ax.text(
            60,
            955 + index * 26,
            text,
            color=INK,
            fontproperties=FONT,
            fontsize=9.5,
            va="center",
        )

    ax.add_patch(
        Rectangle(
            (780, 900),
            880,
            220,
            facecolor="#FFFBEB",
            edgecolor="#F59E0B",
            linewidth=1,
        )
    )
    ax.text(
        800,
        925,
        "建模说明",
        color="#B45309",
        fontproperties=FONT_BOLD,
        fontsize=12,
        va="center",
    )
    notes = [
        "OrderDetail.subtotal 是 PERSISTED 计算列，不再单独维护。",
        "Orders.total_amount 是反规范化汇总，由下单事务写入并与明细保持一致。",
        "Inventory.product_id 唯一，因此 Product 与 Inventory 是 1 : 0..1。",
        "每张订单至少一条明细属于业务规则；数据库外码只保证明细引用有效订单。",
        "会员可为空：散客订单 member_id = NULL，视图中显示为“散客”。",
        "销售出库同时写 OrderDetail 与 InventoryLog，二者在同一事务内完成。",
    ]
    for index, text in enumerate(notes):
        ax.text(
            800,
            955 + index * 24,
            "• " + text,
            color=INK,
            fontproperties=FONT,
            fontsize=9.2,
            va="center",
        )


def main() -> None:
    fig, ax = plt.subplots(figsize=(17, 12), dpi=100)
    ax.set_xlim(0, 1700)
    ax.set_ylim(1200, 0)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    for name, entity in ENTITIES.items():
        draw_entity(ax, name, entity)
    draw_relationships(ax)
    draw_legend(ax)

    ax.text(
        1350,
        1170,
        "PetCare 宠物店管理系统  ER 图（v1.0）",
        color=INK,
        fontproperties=FONT_BOLD,
        fontsize=13,
        ha="right",
        va="center",
    )

    fig.tight_layout(pad=0.4)
    fig.savefig(ROOT / "petcare_er.svg", format="svg", bbox_inches="tight")
    fig.savefig(ROOT / "petcare_er.png", format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"written {ROOT / 'petcare_er.svg'}")
    print(f"written {ROOT / 'petcare_er.png'}")


if __name__ == "__main__":
    main()
