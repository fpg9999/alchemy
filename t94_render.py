# -*- coding: utf-8 -*-
"""T94-B 出图：完美膜 + 自制造自修复（读 t94_life.json / t94_<arm>.json）。

图：
  images/t94_life_snapshots.png  终态快照（主体/膜/食物/环境分色）
  images/t94_life_protect.png    主体存留、主体原子、外来接触与核心-外来反应
  images/t94_life_membrane.png   膜覆盖率、膜存活、贴附比例、食物
  images/t94_life_react.png      内部/壳/外部反应率与累计反应
  images/t94_life_selfrepair.png 自修复臂：膜补充/消耗、birth/death、repair
中文用 msyh.ttc / msyhbd.ttc，避免乱码。
"""
from __future__ import annotations

import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
IMGDIR = os.path.join(BASE, "images")
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONTB = r"C:\Windows\Fonts\msyhbd.ttc"

INK = (28, 28, 36)
SUB = (92, 92, 102)
GRID = (222, 224, 230)
AXIS = (60, 60, 70)
RED = (200, 44, 44)
BLUE = (40, 92, 200)
ORANGE = (228, 142, 32)
TEAL = (26, 150, 140)
PURPLE = (140, 80, 168)
GRAY = (120, 120, 130)
GREEN = (40, 150, 70)
MAGENTA = (200, 60, 150)
BROWN = (150, 110, 60)
CYAN = (30, 160, 190)

# 臂配色与短标签
COL = {
    "no_membrane_dyn": GRAY,
    "membrane_PK_dyn": BLUE,
    "membrane_PK_FO": MAGENTA,
    "oxc_shell_FO": ORANGE,
    "membrane_PK_selfrepair": TEAL,
    "membrane_PK_dyn_G0": GREEN,
    "membrane_W2_bal": PURPLE,
    "membrane_W2_dyn": CYAN,
    "membrane_PK_OKbody_dyn": BROWN,
    "membrane_WA2_OKbody_dyn": RED,
}
LAB = {
    "no_membrane_dyn": "无膜 + 富动素",
    "membrane_PK_dyn": "PK膜 + 富动素 (G=0.2)",
    "membrane_PK_FO": "PK膜 + 富F/O",
    "oxc_shell_FO": "旧OXC壳 + 富F/O",
    "membrane_PK_selfrepair": "自修复 PK膜",
    "membrane_PK_dyn_G0": "PK膜 + 富动素 (G=0)",
    "membrane_W2_bal": "轻膜W2 + 均衡",
    "membrane_W2_dyn": "轻膜W2 + 富动素",
    "membrane_PK_OKbody_dyn": "PK膜 + OK主体",
    "membrane_WA2_OKbody_dyn": "WA2膜 + OK主体 (可维持组合)",
}
ROLE_COL = {
    "body": RED,
    "membrane": BLUE,
    "food": ORANGE,
    "env": GRAY,
    "other": PURPLE,
}


def fnt(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def load(name):
    with open(os.path.join(BASE, name), "r", encoding="utf-8") as f:
        return json.load(f)


def axes(d, box, ymax, ylab, xlab, xmax=600.0, fmt="%.0f", ymin=0.0):
    x0, y0, x1, y1 = box
    d.rectangle([x0, y0, x1, y1], outline=AXIS, width=2)
    for i in range(5):
        v = ymin + (ymax - ymin) * i / 4.0
        y = y1 - (y1 - y0) * i / 4.0
        d.line([(x0, y), (x1, y)], fill=GRID, width=1)
        d.text((x0 - 10, y - 10), fmt % v, font=fnt(16), fill=SUB, anchor="ra")
    for i in range(5):
        v = xmax * i / 4.0
        x = x0 + (x1 - x0) * i / 4.0
        d.line([(x, y0), (x, y1)], fill=GRID, width=1)
        d.text((x, y1 + 8), "%.0f" % v, font=fnt(16), fill=SUB, anchor="ma")
    d.text((x0 - 78, (y0 + y1) / 2), ylab, font=fnt(16), fill=SUB, anchor="mm")
    d.text(((x0 + x1) / 2, y1 + 34), xlab, font=fnt(16), fill=SUB, anchor="ma")


def line(d, box, xs, ys, xmax, ymax, col, w=3, ymin=0.0):
    x0, y0, x1, y1 = box
    pts = []
    for x, y in zip(xs, ys):
        if y is None:
            continue
        px = x0 + (x1 - x0) * (x / float(xmax))
        py = y1 - (y1 - y0) * ((y - ymin) / float(ymax - ymin))
        pts.append((px, py))
    if len(pts) >= 2:
        d.line(pts, fill=col, width=w, joint="curve")


def bars_h(d, x0, y0, items, w=520, h=24, dy=38, vmax=None, fmt="%.1f"):
    vmax = vmax or max([abs(v) for _, v, _ in items] + [1e-9])
    for i, (label, v, col) in enumerate(items):
        y = y0 + i * dy
        d.text((x0, y + h / 2), label, font=fnt(15), fill=INK, anchor="lm")
        bw = int(w * min(1.0, abs(v) / vmax))
        if bw > 0:
            d.rectangle([x0 + 380, y, x0 + 380 + bw, y + h], fill=col)
        d.text((x0 + 390 + bw, y + h / 2), fmt % v, font=fnt(14), fill=SUB, anchor="lm")


def legend(d, x, y, items, dy=24):
    for i, (label, col) in enumerate(items):
        yy = y + i * dy
        d.line([(x, yy + 8), (x + 26, yy + 8)], fill=col, width=4)
        d.text((x + 34, yy), label, font=fnt(15), fill=INK)


def rate(ss, key, win=100):
    xs, ys = [], []
    for i, p in enumerate(ss):
        t = p["t"]
        if t > 0 and t % win == 0:
            q = ss[max(0, i - win // 10)]
            xs.append(t)
            ys.append(p[key] - q[key])
    return xs, ys


def fig_snapshots(main, arms):
    names = ["no_membrane_dyn", "membrane_PK_dyn", "membrane_PK_dyn_G0",
             "membrane_WA2_OKbody_dyn"]
    img = Image.new("RGB", (2400, 1300), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((80, 40), "T94-B：终态快照——主体（红）/ 膜（蓝）/ 食物（橙）/ 环境（灰）",
           font=fnt(30, True), fill=INK)
    d.text((80, 88),
           "世界 160×110；主体冻结在中心；膜环 R=7~12；环境从 R>13.5 按群系元素丰度采样。",
           font=fnt(17), fill=SUB)
    boxes = [(80, 160, 1130, 620), (1290, 160, 2340, 620),
             (80, 720, 1130, 1180), (1290, 720, 2340, 1180)]
    for name, box in zip(names, boxes):
        arm = load("t94_%s.json" % name)
        fs = arm["final_state"]
        W, H = fs["W"], fs["H"]
        x0, y0, x1, y1 = box
        d.rectangle([x0, y0, x1, y1], outline=AXIS, width=2)
        sc = min((x1 - x0) / (W + 4.0), (y1 - y0) / (H + 4.0))
        ox = x0 + ((x1 - x0) - W * sc) / 2.0
        oy = y0 + ((y1 - y0) - H * sc) / 2.0
        # 参考圆 R=7/12
        ctr = fs["center"]
        for rr in (7.0, 12.0):
            cx = ox + (ctr[1] + 0.5) * sc
            cy = oy + (ctr[0] + 0.5) * sc
            d.ellipse([cx - rr * sc, cy - rr * sc, cx + rr * sc, cy + rr * sc],
                      outline=(205, 210, 225), width=1)
        for r, c, f, role in fs["mols"]:
            px = ox + (c + 0.5) * sc
            py = oy + (r + 0.5) * sc
            col = ROLE_COL.get(role, PURPLE)
            d.rectangle([px - 2.4, py - 2.4, px + 2.4, py + 2.4], fill=col)
        s = arm["summary"]
        d.text((x0, y0 - 34), LAB.get(name, name), font=fnt(19, True), fill=INK)
        d.text((x0, y1 + 10),
               "主体 %d 个 / 膜 %d 个（留存 %.0f%%）/ 角覆盖 %.0f%% / 环境-主体接触 %d / 核心-环境反应 %d"
               % (s["body_n_final"], s["membrane_n_final"],
                  100.0 * (s["membrane_retention"] or 0),
                  100.0 * (s["coverage_ang_final"] or 0),
                  s["contacts_env_body_total"], s["core_env_react_total"]),
               font=fnt(15), fill=SUB)
    d.text((80, 1235),
           "注：灰点=环境分子（含反应后代）；红点=主体物质（A≥2,D=0）；蓝点=膜物质；橙点=内部食物。"
           "「可维持组合」= WA2 轻膜 + OK 主体 + XA3 惰性食物：覆盖率 78%，但膜自斥无锁网、密封性不足（仍有环境-主体接触），见 docs/T94_LIFE_SIM.md。",
           font=fnt(15), fill=SUB)
    img.save(os.path.join(IMGDIR, "t94_life_snapshots.png"))
    print("saved images/t94_life_snapshots.png", img.size)


def fig_protect(main, arms):
    series = main["series"]
    KEY = ["no_membrane_dyn", "membrane_PK_dyn", "membrane_PK_FO",
           "membrane_PK_dyn_G0", "membrane_W2_dyn", "membrane_WA2_OKbody_dyn"]
    img = Image.new("RGB", (2400, 1240), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((80, 36), "T94-B：主体存留与保护效果（p_react=1.0：接触即反应）",
           font=fnt(30, True), fill=INK)
    d.text((80, 84),
           "主体=初始主体及其并入后代（血统+冻结，并入半径 ≤6）；外来=环境分子及其反应后代；A/B/C 同色（6 条代表臂）。",
           font=fnt(17), fill=SUB)

    boxA = (120, 160, 1040, 640)
    d.text((120, 122), "A 主体分子数（个）", font=fnt(18, True), fill=INK)
    ymax = max([p["body_n"] for ss in series.values() for p in ss] + [30])
    ymax = 10 * math.ceil(ymax / 10.0)
    axes(d, boxA, ymax, "", "t（拍）", 600, fmt="%.0f")
    for name in KEY:
        if name not in series:
            continue
        ss = series[name]
        line(d, boxA, [p["t"] for p in ss], [p["body_n"] for p in ss], 600, ymax,
             COL.get(name, GRAY), 3)
    items = [(LAB.get(n, n), COL.get(n, GRAY)) for n in KEY if n in series]
    legend(d, boxA[0] + 14, boxA[3] - 84, items[:3])
    legend(d, boxA[0] + 330, boxA[3] - 84, items[3:])

    boxB = (1300, 160, 2220, 640)
    d.text((1300, 122), "B 主体原子数（个）", font=fnt(18, True), fill=INK)
    ymax = max([p["body_atoms"] for ss in series.values() for p in ss] + [30])
    ymax = 10 * math.ceil(ymax / 10.0)
    axes(d, boxB, ymax, "", "t（拍）", 600, fmt="%.0f")
    for name in KEY:
        if name not in series:
            continue
        ss = series[name]
        line(d, boxB, [p["t"] for p in ss], [p["body_atoms"] for p in ss], 600,
             ymax, COL.get(name, GRAY), 3)

    boxC = (120, 760, 1040, 1060)
    d.text((120, 722), "C 环境-主体接触累计（相邻对数）", font=fnt(18, True), fill=INK)
    cmax = max([a["contacts_env_body_total"] for a in arms] + [10])
    cmax = 500 * math.ceil(cmax / 500.0)
    axes(d, boxC, cmax, "", "t（拍）", 600, fmt="%.0f")
    for name in KEY:
        if name in series:
            ss = series[name]
            line(d, boxC, [p["t"] for p in ss],
                 [p["contacts_env_body_cum"] for p in ss], 600, cmax,
                 COL.get(name, GRAY), 3)

    boxD = (1300, 700, 2340, 1180)
    d.text((1300, 662), "D 核心-环境反应与主体原子留存", font=fnt(18, True), fill=INK)
    d.text((1300, 698), "核心-环境反应（原始计数，10 臂）", font=fnt(16), fill=SUB)
    ordered = sorted(arms, key=lambda a: a["core_env_react_total"])
    items = [(LAB.get(a["name"], a["name"]),
              a["core_env_react_total"], COL.get(a["name"], GRAY)) for a in ordered]
    bars_h(d, 1300, 730, items, w=520, h=20, dy=30, vmax=8.0, fmt="%d")
    d.text((1300, 1046), "主体原子留存（终/初，5 条代表臂）", font=fnt(16), fill=SUB)
    for i, name in enumerate(KEY[:5]):
        a = [x for x in arms if x["name"] == name][0]
        y = 1064 + i * 24
        r = (a["body_atoms_final"] or 0) / float(a["body_atoms0"] or 1)
        d.text((1300, y), "%-26s %d→%d (%.0f%%)"
               % (LAB.get(name, name), a["body_atoms0"],
                  a["body_atoms_final"], 100 * r), font=fnt(14), fill=SUB)

    d.text((120, 1206),
           "读法：无膜臂靠食物 XA3 自缩合生长（A2/XA2 并入，原子 48→102），但环境-主体接触 6542；"
           "PK 膜在 G=0 时接触降到 0、核心-环境反应 0，在 G=0.2 时膜沉降失效。接触为累计原始计数，不做百分比外推。",
           font=fnt(15), fill=SUB)
    img.save(os.path.join(IMGDIR, "t94_life_protect.png"))
    print("saved images/t94_life_protect.png", img.size)


def fig_membrane(main, arms):
    series = main["series"]
    KEY = ["membrane_PK_dyn", "membrane_PK_FO", "membrane_PK_dyn_G0",
           "membrane_W2_dyn", "membrane_WA2_OKbody_dyn",
           "membrane_PK_selfrepair", "oxc_shell_FO"]
    img = Image.new("RGB", (2400, 1240), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((80, 36), "T94-B：膜是否铺展、是否被主体拉住、是否存活",
           font=fnt(30, True), fill=INK)
    d.text((80, 84),
           "角覆盖 = 绕核心 36 个扇区中有膜分子的比例；贴附 = 距主体 ≤2 格内膜分子比例；A/B 同色。",
           font=fnt(17), fill=SUB)

    boxA = (120, 160, 1010, 620)
    d.text((120, 122), "A 膜角覆盖（36 扇区）", font=fnt(18, True), fill=INK)
    axes(d, boxA, 1.0, "", "t（拍）", 600, fmt="%.2f")
    for name, ss in series.items():
        if name not in KEY:
            continue
        line(d, boxA, [p["t"] for p in ss], [p["coverage_ang"] for p in ss],
             600, 1.0, COL.get(name, GRAY), 3)
    legend(d, 1032, 180,
           [(LAB.get(n, n), COL.get(n, GRAY)) for n in KEY if n in series], dy=25)

    boxB = (1340, 160, 2230, 620)
    d.text((1340, 122), "B 膜分子数（个，含反应后代）", font=fnt(18, True), fill=INK)
    ymax = max([p["membrane_n"] for ss in series.values() for p in ss] + [30])
    ymax = 40 * math.ceil(ymax / 40.0)
    axes(d, boxB, ymax, "", "t（拍）", 600, fmt="%.0f")
    for name, ss in series.items():
        if name not in KEY:
            continue
        line(d, boxB, [p["t"] for p in ss], [p["membrane_n"] for p in ss], 600,
             ymax, COL.get(name, GRAY), 3)

    d.text((120, 700), "C 膜留存率（终/初）", font=fnt(18, True), fill=INK)
    items = []
    for a in sorted(arms, key=lambda a: -(a["membrane_retention"] or 0)):
        if (a["membrane_n0"] or 0) <= 0:
            continue
        items.append((LAB.get(a["name"], a["name"]),
                      100.0 * (a["membrane_retention"] or 0), COL.get(a["name"], GRAY)))
    bars_h(d, 120, 745, items, w=520, h=22, dy=34, vmax=100.0, fmt="%.0f%%")

    boxD = (1340, 700, 2230, 1060)
    d.text((1340, 662), "D 膜被主体吸引：贴附比例（距主体≤2 格）", font=fnt(18, True), fill=INK)
    axes(d, boxD, 1.0, "", "t（拍）", 600, fmt="%.2f")
    for name in ("membrane_PK_dyn", "membrane_PK_dyn_G0",
                 "membrane_W2_dyn", "membrane_WA2_OKbody_dyn"):
        if name in series:
            ss = series[name]
            line(d, boxD, [p["t"] for p in ss], [p["membrane_attached"] for p in ss],
                 600, 1.0, COL.get(name, GRAY), 3)

    d.text((120, 1156),
           "读法：PK（A=0,D=3,mass=1.5）被主体强吸引并贴附，但 G=0.2 下整体下沉、角覆盖衰减；"
           "W2/WA2 质量 0，在默认重力下仍维持环带。自修复臂的膜补充不足以抵消壳-环境反应消耗。",
           font=fnt(15), fill=SUB)
    img.save(os.path.join(IMGDIR, "t94_life_membrane.png"))
    print("saved images/t94_life_membrane.png", img.size)


def fig_react(main, arms):
    series = main["series"]
    KEY = ["no_membrane_dyn", "membrane_PK_dyn", "membrane_PK_FO",
           "membrane_PK_dyn_G0", "membrane_W2_dyn", "membrane_WA2_OKbody_dyn",
           "membrane_PK_selfrepair"]
    img = Image.new("RGB", (2400, 1180), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((80, 36), "T94-B：内部 / 膜带 / 外部反应率（每 100 拍原始计数）",
           font=fnt(30, True), fill=INK)
    d.text((80, 84), "反应按组质心到核心距离分类：内部 ≤R_INTERIOR、膜带 R_INTERIOR~R_SHELL、外部 >R_SHELL；A/B 同色。",
           font=fnt(17), fill=SUB)

    for k, (key, title) in enumerate((("internal_react_cum", "A 内部反应（膜内）"),
                                      ("env_react_cum", "B 外部反应（环境中）"))):
        box = (120 + k * 1180, 160, 1000 + k * 1180, 700)
        d.text((box[0], 106), title, font=fnt(18, True), fill=INK)
        rmax = 1
        for name in KEY:
            if name not in series:
                continue
            rd = rate(series[name], key)
            if rd[1]:
                rmax = max(rmax, max(rd[1]))
        step = 50 if rmax > 150 else (20 if rmax > 40 else 10)
        ymx = step * math.ceil(rmax / float(step))
        axes(d, box, ymx, "次/100 拍", "t（拍）", 600, fmt="%.0f")
        for name in KEY:
            if name not in series:
                continue
            xs, ys = rate(series[name], key)
            if xs:
                line(d, box, xs, ys, 600, ymx, COL.get(name, GRAY), 3)
    legend(d, 1046, 190,
           [(LAB.get(n, n), COL.get(n, GRAY)) for n in KEY if n in series], dy=25)

    boxC = (120, 780, 1040, 1080)
    d.text((120, 742), "C 核心-环境反应累计（主体被环境化学消耗）", font=fnt(18, True), fill=INK)
    cmax = max([a["core_env_react_total"] for a in arms] + [5])
    cmax = 2 * math.ceil(cmax / 2.0)
    axes(d, boxC, cmax, "", "t（拍）", 600, fmt="%.0f")
    for name in ("no_membrane_dyn", "oxc_shell_FO", "membrane_PK_dyn",
                 "membrane_PK_dyn_G0", "membrane_WA2_OKbody_dyn"):
        if name in series:
            ss = series[name]
            line(d, boxC, [p["t"] for p in ss], [p["core_env_react_cum"] for p in ss],
                 600, cmax, COL.get(name, GRAY), 3)

    d.text((1300, 742), "D 终态累计反应构成（内部 / 膜带 / 外部）", font=fnt(18, True), fill=INK)
    for i, a in enumerate(sorted(arms, key=lambda a: -a["n_react_total"])):
        y = 780 + i * 34
        d.text((1300, y), LAB.get(a["name"], a["name"])[:26], font=fnt(14), fill=INK)
        x = 1720
        tot = max(1, a["n_react_total"])
        for key, col in (("internal_react_total", TEAL), ("shell_react_total", BLUE),
                         ("env_react_total", GRAY)):
            bw = int(300 * (a[key] or 0) / float(tot))
            if bw > 0:
                d.rectangle([x, y - 1, x + bw, y + 17], fill=col)
                x += bw
        d.text((2030, y), "共 %d（内 %d / 膜 %d / 外 %d）"
               % (tot, a["internal_react_total"], a["shell_react_total"],
                  a["env_react_total"]), font=fnt(13), fill=SUB)

    d.text((120, 1142),
           "读法：p_react=1.0 使「接触即反应」；膜带反应高说明膜本身是反应界面（被消耗），"
           "核心-环境反应低说明主体被保护。前 100 拍的爆发来自 T0=200°C 的初始高温窗口。",
           font=fnt(15), fill=SUB)
    img.save(os.path.join(IMGDIR, "t94_life_react.png"))
    print("saved images/t94_life_react.png", img.size)


def fig_selfrepair(main, arms):
    series = main["series"]
    img = Image.new("RGB", (2400, 1240), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((80, 36), "T94-B：自制造 / 自修复——膜补充能否抵消消耗",
           font=fnt(30, True), fill=INK)
    d.text((80, 84),
           "自修复臂：初始 PK 膜只有 140 个（其余臂 220），内部食物 P2K4 45 个；"
           "路径 O2 + P2K4 → 2 OK + 2 PK（T_local≥40°C 才发生）。",
           font=fnt(17), fill=SUB)

    boxA = (120, 160, 1040, 620)
    d.text((120, 122), "A 膜分子数：自修复臂 vs 对照", font=fnt(18, True), fill=INK)
    ymax = max([p["membrane_n"] for ss in series.values() for p in ss] + [40])
    ymax = 40 * math.ceil(ymax / 40.0)
    axes(d, boxA, ymax, "膜分子数", "t（拍）", 600, fmt="%.0f")
    for name in ("membrane_PK_selfrepair", "membrane_PK_dyn",
                 "membrane_PK_dyn_G0", "membrane_WA2_OKbody_dyn"):
        if name in series:
            ss = series[name]
            line(d, boxA, [p["t"] for p in ss], [p["membrane_n"] for p in ss],
                 600, ymax, COL.get(name, GRAY), 3)
    legend(d, 1052, 190,
           [(LAB.get(n, n), COL.get(n, GRAY)) for n in
            ("membrane_PK_selfrepair", "membrane_PK_dyn",
             "membrane_PK_dyn_G0", "membrane_WA2_OKbody_dyn")], dy=25)

    boxB = (1300, 160, 2220, 620)
    d.text((1300, 122), "B 自修复臂：birth / death / repair 累计", font=fnt(18, True), fill=INK)
    ss = series["membrane_PK_selfrepair"]
    ymax = max([max(p["birth_mem_cum"], p["death_mem_cum"], p["repair_react_cum"])
                for p in ss] + [10])
    ymax = 20 * math.ceil(ymax / 20.0)
    axes(d, boxB, ymax, "累计次数", "t（拍）", 600, fmt="%.0f")
    line(d, boxB, [p["t"] for p in ss], [p["birth_mem_cum"] for p in ss],
         600, ymax, GREEN, 3)
    line(d, boxB, [p["t"] for p in ss], [p["death_mem_cum"] for p in ss],
         600, ymax, RED, 3)
    line(d, boxB, [p["t"] for p in ss], [p["repair_react_cum"] for p in ss],
         600, ymax, TEAL, 3)
    legend(d, boxB[0] + 14, boxB[1] + 10,
           [("膜生成 birth", GREEN), ("膜死亡 death", RED), ("修复反应 repair", TEAL)])

    # C 自修复臂食物与膜
    boxC = (120, 740, 1040, 1060)
    d.text((120, 702), "C 自修复臂：食物 P2K4 与膜物质", font=fnt(18, True), fill=INK)
    ymax = max([max(p["food_n"], p["membrane_n"]) for p in ss] + [20])
    ymax = 20 * math.ceil(ymax / 20.0)
    axes(d, boxC, ymax, "分子数", "t（拍）", 600, fmt="%.0f")
    line(d, boxC, [p["t"] for p in ss], [p["food_n"] for p in ss], 600, ymax, ORANGE, 3)
    line(d, boxC, [p["t"] for p in ss], [p["membrane_n"] for p in ss], 600, ymax, BLUE, 3)
    legend(d, boxC[2] - 250, boxC[1] + 18,
           [("食物 P2K4", ORANGE), ("膜 PK", BLUE)])

    # D 数字摘要
    a = [x for x in arms if x["name"] == "membrane_PK_selfrepair"][0]
    d.text((1300, 700), "D 自修复臂终态数字", font=fnt(18, True), fill=INK)
    rows = [
        "膜：%d → %d（留存 %.0f%%）" % (a["membrane_n0"], a["membrane_n_final"],
                                        100 * (a["membrane_retention"] or 0)),
        "膜生成 birth：%d 个" % a["birth_mem_total"],
        "膜死亡 death：%d 个" % a["death_mem_total"],
        "修复反应 repair：%d 次" % a["repair_react_total"],
        "食物 P2K4：%d → %d" % (a["food_n0"], a["food_n_final"]),
        "主体：%d → %d 个；原子 %d → %d" % (a["body_n0"], a["body_n_final"],
                                            a["body_atoms0"], a["body_atoms_final"]),
        "核心-环境反应：%d 次；环境-主体接触：%d" % (a["core_env_react_total"],
                                                    a["contacts_env_body_total"]),
        "主力消耗：膜-环境反应 %d 次；内部反应 %d 次"
        % (a["mem_env_react_total"], a["internal_react_total"]),
    ]
    for i, s in enumerate(rows):
        d.text((1300, 745 + i * 36), s, font=fnt(17), fill=SUB)

    d.text((120, 1150),
           "结论：在 600 拍内，自修复臂的膜生成远少于消耗（birth %d vs death %d），"
           "自修复只能延缓、不能维持膜；且修复反应需要 T_local≥40°C，降温平台期后停止。"
           % (a["birth_mem_total"], a["death_mem_total"]),
           font=fnt(15), fill=SUB)
    img.save(os.path.join(IMGDIR, "t94_life_selfrepair.png"))
    print("saved images/t94_life_selfrepair.png", img.size)


def main():
    os.makedirs(IMGDIR, exist_ok=True)
    data = load("t94_life.json")
    arms = data["arms"]
    print("arms:", len(arms), "runtime", data.get("runtime_s"))
    fig_snapshots(data, arms)
    fig_protect(data, arms)
    fig_membrane(data, arms)
    fig_react(data, arms)
    fig_selfrepair(data, arms)
    print("all images ->", IMGDIR)


if __name__ == "__main__":
    main()
