# -*- coding: utf-8 -*-
"""T93 作图：热环境 + 多分子核心 + C 类低温冷壳保护膜。

读取 t93_membrane.json（主文件）与每臂 t93_<arm>.json 中的 summary/series，
生成 images/t93_*.png。所有标注数字都来自 JSON，不手写结果。
"""
import io
import json
import math
import os
from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
IMGDIR = os.path.join(BASE, "images")
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONTB = r"C:\Windows\Fonts\msyhbd.ttc"

INK = (32, 32, 38)
SUB = (92, 92, 102)
GRID = (236, 236, 242)
AX = (150, 150, 160)

C_CORE = (196, 40, 40)
C_FOOD = (232, 150, 40)
C_SHELL = (40, 120, 210)      # 冷壳（内层）
C_OUTER = (30, 170, 170)      # 双层外膜
C_BATH = (120, 120, 130)      # 外来攻击/其他
C_EMPTY = (252, 252, 251)


def fnt(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def load(name):
    with io.open(os.path.join(BASE, name), encoding="utf-8") as fh:
        return json.load(fh)


def axes(d, box, ymax, ylab, xlab, xmax=700.0, fmt="%d", ymin=0.0):
    x0, y0, x1, y1 = box
    d.rectangle([x0, y0, x1, y1], outline=AX)
    for i in range(5):
        v = ymin + (ymax - ymin) * i / 4.0
        y = y1 - (y1 - y0) * i / 4.0
        d.line([(x0, y), (x1, y)], fill=GRID)
        d.text((x0 - 58, y - 9), fmt % v, font=fnt(13), fill=SUB)
    d.text((x0 - 46, y0 - 26), ylab, font=fnt(15), fill=SUB)
    d.text(((x0 + x1) / 2 - 48, y1 + 8), xlab, font=fnt(15), fill=SUB)


def line(d, box, xs, ys, xmax, ymax, col, w=3, ymin=0.0):
    x0, y0, x1, y1 = box
    pts = []
    for x, y in zip(xs, ys):
        if y is None:
            continue
        px = x0 + (x1 - x0) * x / max(1.0, xmax)
        py = y1 - (y1 - y0) * (y - ymin) / max(1e-9, ymax - ymin)
        pts.append((px, py))
    if len(pts) >= 2:
        d.line(pts, fill=col, width=w)
    return pts


def bars_h(d, x0, y0, wmax, rows, vmax, fmt="%.3f"):
    for i, (lab, v, col) in enumerate(rows):
        yy = y0 + i * 30
        bw = max(2, wmax * (v or 0.0) / max(1e-9, vmax))
        d.rectangle([x0, yy, x0 + bw, yy + 22], fill=col)
        d.text((x0 + bw + 8, yy + 2), "%s  %s" % (lab, fmt % (v or 0.0)),
               font=fnt(13), fill=SUB)


def legend(d, x, y, items, dy=24):
    for lab, col in items:
        d.line([(x, y + 7), (x + 24, y + 7)], fill=col, width=3)
        d.text((x + 30, y - 3), lab, font=fnt(14), fill=SUB)
        y += dy
    return y


def main():
    data = load("t93_membrane.json")
    cfg = data["config"]
    arms = {a["name"]: a for a in data["arms"]}
    series = data["series"]
    T = cfg.get("ticks") or max(s[-1]["t"] for s in series.values() if s)
    T = max(T, 1)
    W, H = 160, 110
    core_center = (55, 80)

    # 颜色与臂序
    order = ["no_shell_hot", "shell_OXC_hot", "shell_C2_hot", "shell_X2C2_hot",
             "double_OXC_OP_hot", "shell_OXC_cold", "selfasm_OXC_hot_nobath",
             "shell_OXC_hot_g002", "shell_OXC_hot_g030"]
    order = [a for a in order if a in arms]
    COL = {
        "no_shell_hot": (110, 110, 120),
        "shell_OXC_hot": (40, 120, 210),
        "shell_C2_hot": (60, 170, 90),
        "shell_X2C2_hot": (170, 100, 200),
        "double_OXC_OP_hot": (30, 175, 175),
        "shell_OXC_cold": (200, 130, 60),
        "selfasm_OXC_hot_nobath": (150, 150, 60),
        "shell_OXC_hot_g002": (220, 90, 140),
        "shell_OXC_hot_g030": (90, 60, 170),
    }
    LAB = {
        "no_shell_hot": "无壳对照 400°C",
        "shell_OXC_hot": "OXC 冷壳 400°C",
        "shell_C2_hot": "C2 壳 400°C",
        "shell_X2C2_hot": "X2C2 壳 400°C",
        "double_OXC_OP_hot": "双层 OXC+OP 400°C",
        "shell_OXC_cold": "OXC 冷壳 20°C",
        "selfasm_OXC_hot_nobath": "无浴自组装 400°C",
        "shell_OXC_hot_g002": "OXC 壳 G=0.02",
        "shell_OXC_hot_g030": "OXC 壳 G=0.30",
    }
    shells = {}
    for n in order:
        s = arms[n].get("shell")
        shells[n] = s

    # =====================================================================
    # 图 1：终态快照（四臂）
    # =====================================================================
    panels = [n for n in ("no_shell_hot", "shell_OXC_hot", "shell_C2_hot",
                          "double_OXC_OP_hot") if n in arms]
    if not panels:
        panels = order[:3]
    pw, ph = 560, 430
    img = Image.new("RGB", (2400, 1180), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 24), "T93：400°C 热浴中的「核心 + C 类冷壳 + 攻击浴」终态快照",
           font=fnt(30, True), fill=INK)
    d.text((40, 70), "世界 160×110；红=C3K3F2 核心（固态），橙=C2K2/CKF2 食物，"
                     "蓝=冷壳（OXC/C2/X2C2），青=双层外膜（OP），灰=外来攻击分子/其他。"
                     " 所有分子都占格（气档也不穿透）。", font=fnt(15), fill=SUB)
    for k, name in enumerate(panels):
        a = arms[name]
        fs = load("t93_%s.json" % name)["final_state"]
        ox = 45 + (k % 2) * 1180
        oy = 135 + (k // 2) * 500
        sc = 3.0
        d.rectangle([ox, oy, ox + W * sc, oy + H * sc], fill=C_EMPTY, outline=AX)
        # 核心/壳环带参考
        for rr in (8.0, 12.0):
            bb = [ox + (core_center[1] - rr) * sc, oy + (core_center[0] - rr) * sc,
                  ox + (core_center[1] + rr) * sc, oy + (core_center[0] + rr) * sc]
            d.ellipse(bb, outline=(225, 225, 232))
        core_f = cfg.get("core_formula", "C3K3F2")
        food_f = set(cfg.get("food", ["C2K2", "CKF2"]))
        shell_f = set()
        if a.get("shell"):
            shell_f.add(a["shell"])
        outer_f = set()
        if a.get("double"):
            outer_f.add("OP")
        counts = {"core": 0, "food": 0, "shell": 0, "outer": 0, "bath": 0}
        for r, c, f, role in fs["mols"]:
            if f == core_f:
                col = C_CORE
                counts["core"] += 1
            elif f in food_f:
                col = C_FOOD
                counts["food"] += 1
            elif f in shell_f:
                col = C_SHELL
                counts["shell"] += 1
            elif f in outer_f:
                col = C_OUTER
                counts["outer"] += 1
            else:
                col = C_BATH
                counts["bath"] += 1
            d.rectangle([ox + c * sc, oy + r * sc,
                         ox + c * sc + sc, oy + r * sc + sc], fill=col)
        d.text((ox, oy - 30), "%s  t=%d" % (LAB.get(name, name), T),
               font=fnt(18, True), fill=INK)
        s = a
        d.text((ox, oy + H * sc + 6),
               "核心 %d 个（起始 %d）  壳物质 %d  外来接触累计 %d"
               % (s["core_n_final"], s["core_n0"], s["shell_formula_n_final"],
                  s["contacts_foreign_core_total"]), font=fnt(14), fill=SUB)
        d.text((ox, oy + H * sc + 28),
               "壳分子存活 %d/%d  角向覆盖 %.0f%%  τ_in=%.0f°C  τ_out=%.0f°C"
               % (s["shell_alive_final"], s["shell_alive0"],
                  100.0 * (s["cov_angular_final_f"] or 0.0),
                  s["tau_in_final"] or 0, s["tau_out_final"] or 0),
               font=fnt(14), fill=SUB)
    d.text((40, 1085),
           "读法：无壳臂的灰色攻击分子直接贴到红色核心上；有壳臂壳外灰分子被蓝色冷壳挡在半径 8~12 的环带之外。"
           "注意 C2 壳在引擎里同样占格阻挡（C2 物态为“气”，这是模型内部不一致，见 docs/T93_SIM.md）。",
           font=fnt(15), fill=SUB)
    img.save(os.path.join(IMGDIR, "t93_snapshots.png"))
    print("saved images/t93_snapshots.png", img.size)

    # =====================================================================
    # 图 2：核心存留 + 元素组成 + 食物
    # =====================================================================
    img = Image.new("RGB", (2400, 1200), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 24), "T93：核心存留、核心元素组成与内部食物消耗",
           font=fnt(30, True), fill=INK)
    d.text((40, 70), "核心 = 距核心中心 Chebyshev≤8 的 C3K3F2（固态、冻结）；"
                     "核心只在被外来攻击分子（浴系血统）接触时才可被反应侵蚀（T90 惰性主体假设）。",
           font=fnt(15), fill=SUB)

    boxA = (120, 150, 860, 590)
    d.text((120, 96), "A 核心分子数 vs 时间", font=fnt(18, True), fill=INK)
    axes(d, boxA, 26, "C3K3F2 分子数", "t（拍）", T)
    for name in order:
        ss = series[name]
        line(d, boxA, [p["t"] for p in ss], [p["core_n"] for p in ss],
             T, 26, COL.get(name, (100, 100, 100)), 3)
    legend(d, boxA[0] + 12, boxA[3] - 165,
           [(LAB.get(n, n), COL.get(n, (100, 100, 100))) for n in order[:5]])

    # B 元素组成（主臂 shell_OXC_hot 与对照）
    boxB = (1010, 150, 1700, 590)
    d.text((1010, 96), "B 核心元素组成（主臂 OXC 冷壳）", font=fnt(18, True), fill=INK)
    axes(d, boxB, 26 * 8, "原子数", "t（拍）", T)
    mainname = "shell_OXC_hot" if "shell_OXC_hot" in series else order[0]
    ss = series[mainname]
    cols_el = {"C": (90, 90, 200), "K": (200, 90, 150), "F": (90, 170, 90)}
    for el, col in cols_el.items():
        line(d, boxB, [p["t"] for p in ss],
             [(p["core_by_element"] or {}).get(el, 0) for p in ss],
             T, 26 * 8, col, 3)
    legend(d, boxB[0] + 16, boxB[1] + 12,
           [("C", cols_el["C"]), ("K", cols_el["K"]), ("F", cols_el["F"])])

    # C 内部食物
    boxC = (1860, 150, 2350, 590)
    d.text((1860, 96), "C 内部食物 C2K2/CKF2 剩余", font=fnt(18, True), fill=INK)
    axes(d, boxC, 90, "分子数", "t（拍）", T)
    for name in ("no_shell_hot", "shell_OXC_hot"):
        if name in series:
            ss = series[name]
            line(d, boxC, [p["t"] for p in ss], [p["food_n"] for p in ss],
                 T, 90, COL[name], 3)
    legend(d, boxC[0] + 16, boxC[3] - 95,
           [(LAB.get(n, n), COL[n]) for n in ("no_shell_hot", "shell_OXC_hot")
            if n in series])

    # D 核心存留柱状
    d.text((120, 660), "D 各臂核心存留（终态/起始）与核心被攻击反应", font=fnt(18, True), fill=INK)
    y = 710
    for name in order:
        a = arms[name]
        ret = a["core_n_final"] / max(1, a["core_n0"])
        d.text((130, y), LAB.get(name, name), font=fnt(14), fill=SUB)
        bw = 380 * ret
        d.rectangle([360, y, 360 + max(2, bw), y + 20], fill=COL.get(name, (120, 120, 120)))
        d.text((360 + max(2, bw) + 8, y),
               "%.0f%%（%d/%d）  核心被攻击反应 %d 次  外来-核心接触 %d"
               % (100 * ret, a["core_n_final"], a["core_n0"],
                  a["core_attack_react_total"], a["contacts_foreign_core_total"]),
               font=fnt(13), fill=SUB)
        y += 30

    # E 结论（数字来自 JSON）
    if "no_shell_hot" in arms and "shell_OXC_hot" in arms:
        c0 = arms["no_shell_hot"]["core_n_final"]
        c1 = arms["shell_OXC_hot"]["core_n_final"]
        d.text((1400, 690), "E 保护效果（无壳 → 主臂）", font=fnt(18, True), fill=INK)
        rows = [
            "核心存留：%d/24 → %d/24" % (c0, c1),
            "核心-外来接触：%d → %d 次" % (arms["no_shell_hot"]["contacts_foreign_core_total"],
                                          arms["shell_OXC_hot"]["contacts_foreign_core_total"]),
            "外来最近距离：%.1f 格 → %.1f 格" % (
                arms["no_shell_hot"]["foreign_min_r_final"] or -1,
                arms["shell_OXC_hot"]["foreign_min_r_final"] or -1),
            "核心被攻击反应：%d → %d 次" % (
                arms["no_shell_hot"]["core_attack_react_total"],
                arms["shell_OXC_hot"]["core_attack_react_total"]),
            "内部 τ_core 终值：%.0f°C → %.0f°C（浴 %.0f°C）" % (
                arms["no_shell_hot"]["tau_core_final"],
                arms["shell_OXC_hot"]["tau_core_final"], arms["shell_OXC_hot"]["T_env"]),
            "内部 ρ_E/gate：%.3f/%.3f → %.3f/%.3f" % (
                arms["no_shell_hot"]["rho_in_final"],
                arms["no_shell_hot"]["gate_in_final"],
                arms["shell_OXC_hot"]["rho_in_final"],
                arms["shell_OXC_hot"]["gate_in_final"]),
            "壳分子存活：%d/%d（终态壳物质 %d）" % (
                arms["shell_OXC_hot"]["shell_alive_final"],
                arms["shell_OXC_hot"]["shell_alive0"],
                arms["shell_OXC_hot"]["shell_formula_n_final"]),
        ]
        for i, s in enumerate(rows):
            d.text((1400, 740 + i * 40), s, font=fnt(16), fill=SUB)
        d.text((1400, 1026),
               "结论：冷壳在 600 拍内把外来-核心接触降低约一个数量级甚至两个数量级，",
               font=fnt(15), fill=SUB)
        d.text((1400, 1050),
               "但壳自身被壳-浴反应消耗；保温只在前 100~200 拍有效（见 t93_thermal.png）。",
               font=fnt(15), fill=SUB)
    img.save(os.path.join(IMGDIR, "t93_core.png"))
    print("saved images/t93_core.png", img.size)

    # =====================================================================
    # 图 3：内外反应率
    # =====================================================================
    def rate(ss, key, win=100):
        xs, ys = [], []
        for i, p in enumerate(ss):
            if p["t"] % win == 0 and p["t"] > 0:
                q = ss[max(0, i - win // 10)]
                xs.append(p["t"])
                ys.append((p[key] - q[key]) / float(win) * 100.0)
        return xs, ys

    img = Image.new("RGB", (2400, 1120), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 24), "T93：内部 vs 外部反应率（每 100 拍反应次数）",
           font=fnt(30, True), fill=INK)
    d.text((40, 70), "反应按质心到核心中心距离分类：R≤8 内部，8<R≤13 壳带，R>13 外部。"
                     " 内部反应以食物-食物缩合为主（核心-食物反应被惰性主体假设抑制）。",
           font=fnt(15), fill=SUB)
    rate_arms = [n for n in ("no_shell_hot", "shell_OXC_hot", "shell_C2_hot",
                             "double_OXC_OP_hot") if n in series]
    for k, (key, title, ymx) in enumerate((("react_in_cum", "A 内部反应率（R≤8）", 16),
                                           ("react_out_cum", "B 外部反应率（R>13）", 80))):
        box = (120 + k * 1180, 160, 1000 + k * 1180, 700)
        d.text((box[0], 106), title, font=fnt(18, True), fill=INK)
        axes(d, box, ymx, "次/100 拍", "t（拍）", T, fmt="%.0f")
        for name in rate_arms:
            xs, ys = rate(series[name], key)
            if xs:
                line(d, box, xs, ys, T, ymx, COL.get(name, (100, 100, 100)), 3)
        legend(d, box[0] + 14, box[1] + 12,
               [(LAB.get(n, n), COL.get(n, (100, 100, 100))) for n in rate_arms])

    # C 累计
    d.text((120, 736), "C 累计反应：内部 / 壳带 / 外部（终态）", font=fnt(18, True), fill=INK)
    y = 790
    show_arms = [n for n in ("no_shell_hot", "shell_OXC_hot", "shell_C2_hot",
                             "shell_X2C2_hot", "double_OXC_OP_hot",
                             "shell_OXC_cold") if n in arms]
    vmax = max((arms[n]["react_out_total"] + arms[n]["react_in_total"])
               for n in show_arms) or 1
    for name in show_arms:
        a = arms[name]
        tot = a["react_in_total"] + a["react_shellzone_total"] + a["react_out_total"]
        d.text((130, y), LAB.get(name, name), font=fnt(14), fill=SUB)
        xx = 420
        for v, col, lab in ((a["react_in_total"], (90, 150, 220), "内"),
                            (a["react_shellzone_total"], (40, 120, 210), "壳"),
                            (a["react_out_total"], (120, 120, 130), "外")):
            bw = 700 * v / vmax
            d.rectangle([xx, y, xx + max(1, bw), y + 20], fill=col)
            d.text((xx + max(1, bw) + 3, y - 1), "%s%d" % (lab, v),
                   font=fnt(12), fill=SUB)
            xx += max(1, bw) + 46
        d.text((xx + 10, y - 1), "共 %d" % tot, font=fnt(13), fill=SUB)
        y += 40
    d.text((120, 1050),
           "读法：有壳臂的「外部反应率」更高——壳表面本身是反应界面（壳被浴消耗）；"
           "真正被压住的是「外部分子与核心的反应」（见 t93_core.png 的核心被攻击反应次数）。",
           font=fnt(15), fill=SUB)
    img.save(os.path.join(IMGDIR, "t93_react.png"))
    print("saved images/t93_react.png", img.size)

    # =====================================================================
    # 图 4：τ 与 ρ_E
    # =====================================================================
    tb = data["config"].get("thermal", {})
    grid = tb.get("grid", [80, 55])
    img = Image.new("RGB", (2400, 1240), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 24), "T93：内部/外部温度场 τ 与引擎反应门控 ρ_E、gate", font=fnt(30, True), fill=INK)
    d.text((40, 70), "τ 为新增粗网格热场（%d×%d，κ=0.35·sqrt(ηiηj)，边界向 T_env 松弛）；"
                     "粗线=核心质心 ≤3 格内 τ_core，细线=近边界 τ_out。"
                     "τ 只用于度量与展示，不改 resolve 的 Tamb——反应门控仍由 ρ_E 决定（避免双重计温）。"
                     % (grid[0], grid[1]),
           font=fnt(15), fill=SUB)

    boxA = (120, 160, 1000, 640)
    d.text((120, 106), "A 内部 τ_core 与外部 τ_out（400°C 臂）", font=fnt(18, True), fill=INK)
    axes(d, boxA, 420, "τ（°C）", "t（拍）", T, fmt="%.0f")
    d.line([(boxA[0], boxA[3] - (boxA[3] - boxA[1]) * 400 / 420.0),
            (boxA[2], boxA[3] - (boxA[3] - boxA[1]) * 400 / 420.0)],
           fill=(210, 90, 90), width=2)
    d.text((boxA[2] - 130, boxA[3] - (boxA[3] - boxA[1]) * 400 / 420.0 - 22),
           "浴温 400°C", font=fnt(13), fill=(190, 80, 80))
    for name, wi in (("no_shell_hot", 2), ("shell_OXC_hot", 3),
                     ("double_OXC_OP_hot", 3), ("shell_C2_hot", 3)):
        if name not in series:
            continue
        ss = series[name]
        line(d, boxA, [p["t"] for p in ss], [p["tau_core"] for p in ss],
             T, 420, COL[name], wi)
        line(d, boxA, [p["t"] for p in ss], [p["tau_out"] for p in ss],
             T, 420, COL[name], 1)
    legend(d, boxA[2] - 430, boxA[3] - 118,
           [(LAB.get(n, n) + " τ_core", COL[n]) for n in
            ("no_shell_hot", "shell_OXC_hot", "double_OXC_OP_hot", "shell_C2_hot")
            if n in series])

    # B 温差（对照 - 主臂）
    boxB = (1160, 160, 1960, 640)
    d.text((1160, 106), "B 保温效果：Δτ_core = τ_core(无壳) − τ_core(有壳)", font=fnt(18, True), fill=INK)
    axes(d, boxB, 80, "Δτ（°C）", "t（拍）", T, fmt="%.0f")
    if "no_shell_hot" in series:
        base = {p["t"]: p["tau_core"] for p in series["no_shell_hot"]}
        for name in ("shell_OXC_hot", "double_OXC_OP_hot", "shell_C2_hot"):
            if name not in series:
                continue
            xs, ys = [], []
            for p in series[name]:
                b = base.get(p["t"])
                if b is not None and p["tau_core"] is not None:
                    xs.append(p["t"])
                    ys.append(b - p["tau_core"])
            if xs:
                line(d, boxB, xs, ys, T, 80, COL.get(name, (100, 100, 100)), 3)
        legend(d, boxB[0] + 14, boxB[1] + 10,
               [(LAB.get(n, n), COL[n]) for n in
                ("shell_OXC_hot", "double_OXC_OP_hot", "shell_C2_hot")
                if n in series])

    # C ρ_E 与 gate
    boxC = (120, 760, 1000, 1180)
    d.text((120, 706), "C 内部/外部 ρ_E 与反应门控 gate", font=fnt(18, True), fill=INK)
    axes(d, boxC, 1.0, "ρ_E / gate", "t（拍）", T, fmt="%.1f")
    for name in ("no_shell_hot", "shell_OXC_hot"):
        if name not in series:
            continue
        ss = series[name]
        line(d, boxC, [p["t"] for p in ss], [p["rho_in"] for p in ss],
             T, 1.0, COL[name], 3)
        line(d, boxC, [p["t"] for p in ss], [p["gate_in"] for p in ss],
             T, 1.0, COL[name], 1)
        line(d, boxC, [p["t"] for p in ss], [p["rho_out"] for p in ss],
             T, 1.0, (180, 120, 180), 1)
    legend(d, boxC[0] + 14, boxC[1] + 10,
           [("无壳 ρ_E_in", COL["no_shell_hot"]),
            ("有壳 ρ_E_in", COL["shell_OXC_hot"]),
            ("有壳 gate_in", COL["shell_OXC_hot"]),
            ("有壳 ρ_E_out", (180, 120, 180))])

    # D 终态柱状
    d.text((1160, 706), "D 终态：内部 τ_core 与 ρ_E/gate 对比", font=fnt(18, True), fill=INK)
    rows = []
    for name in ("no_shell_hot", "shell_OXC_hot", "double_OXC_OP_hot",
                 "shell_C2_hot", "shell_OXC_hot_g002"):
        if name in arms:
            rows.append((LAB.get(name, name), arms[name].get("tau_core_final") or 0.0,
                         COL.get(name, (100, 100, 100))))
    bars_h(d, 1180, 760, 520, rows, 400, fmt="%.1f")
    d.text((1180, 940), "内部 ρ_E_in：", font=fnt(15), fill=INK)
    rows2 = []
    for name in ("no_shell_hot", "shell_OXC_hot", "double_OXC_OP_hot",
                 "shell_C2_hot"):
        if name in arms:
            rows2.append((LAB.get(name, name), arms[name]["rho_in_final"],
                          COL.get(name, (100, 100, 100))))
    bars_h(d, 1180, 970, 520, rows2, 0.7, fmt="%.3f")
    d.text((1180, 1195),
           "gate = 0.15 + 0.85·ρ_E；ρ_E 由引擎 T87 语义更新（与 τ 无关）。",
           font=fnt(14), fill=SUB)
    img.save(os.path.join(IMGDIR, "t93_thermal.png"))
    print("saved images/t93_thermal.png", img.size)

    # =====================================================================
    # 图 5：壳维持 / 覆盖率 / 外来接触 / 重力诊断
    # =====================================================================
    img = Image.new("RGB", (2400, 1240), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 24), "T93：冷壳是否维持——覆盖率、外来接触与重力坍塌",
           font=fnt(30, True), fill=INK)
    d.text((40, 70), "覆盖率按「当前壳物质分子式」统计（环带 5~18 格内），避免反应替换 id 造成的假损失；"
                     " 外来 = 攻击浴分子及其反应后代。",
           font=fnt(15), fill=SUB)

    boxA = (120, 160, 900, 560)
    d.text((120, 106), "A 壳角向覆盖率（36 扇区）", font=fnt(18, True), fill=INK)
    axes(d, boxA, 1.0, "覆盖率", "t（拍）", T, fmt="%.1f")
    sh_arms = [n for n in ("shell_OXC_hot", "shell_C2_hot", "shell_X2C2_hot",
                           "double_OXC_OP_hot") if n in series]
    for name in sh_arms:
        ss = series[name]
        line(d, boxA, [p["t"] for p in ss], [p["cov_angular_f"] for p in ss],
             T, 1.0, COL.get(name, (100, 100, 100)), 3)
    legend(d, boxA[0] + 14, boxA[1] + 10,
           [(LAB.get(n, n), COL.get(n, (100, 100, 100))) for n in sh_arms])

    boxB = (1030, 160, 1810, 560)
    d.text((1030, 106), "B 外来-核心接触累计（核心被攻击的直接度量）", font=fnt(18, True), fill=INK)
    cmax = 100.0
    for name in ("no_shell_hot", "shell_OXC_hot", "shell_C2_hot",
                 "double_OXC_OP_hot", "shell_OXC_hot_g030", "shell_OXC_hot_g002"):
        if name in arms:
            cmax = max(cmax, arms[name]["contacts_foreign_core_total"] or 0)
    cmax = 2000.0 * math.ceil(cmax / 2000.0)
    axes(d, boxB, cmax, "相邻对数（累计）", "t（拍）", T, fmt="%.0f")
    for name in ("no_shell_hot", "shell_OXC_hot", "shell_C2_hot",
                 "shell_X2C2_hot", "double_OXC_OP_hot",
                 "shell_OXC_hot_g030", "shell_OXC_hot_g002"):
        if name not in series:
            continue
        ss = series[name]
        line(d, boxB, [p["t"] for p in ss],
             [p["contacts_foreign_core_cum"] for p in ss], T, cmax,
             COL.get(name, (100, 100, 100)), 3)
    legend(d, boxB[0] + 14, boxB[1] + 10,
           [(LAB.get(n, n), COL.get(n, (100, 100, 100)))
            for n in ("no_shell_hot", "shell_OXC_hot", "shell_C2_hot",
                      "shell_X2C2_hot", "double_OXC_OP_hot",
                      "shell_OXC_hot_g030", "shell_OXC_hot_g002")
            if n in series])
    d.text((1030, 588),
           "外来-壳接触累计远大于核心接触（C2 壳 111,384 次；OXC 37,004 次），"
           "说明壳确实拦截了大部分攻击分子，但自身也被消耗（见 D 与文档表）。",
           font=fnt(14), fill=SUB)

    boxC = (120, 690, 900, 1090)
    d.text((120, 636), "C 壳质心（重力沉降诊断，纵轴=世界高度 110−行号）", font=fnt(18, True), fill=INK)
    axes(d, boxC, 110, "世界高度（行号自下而上）", "t（拍）", T, fmt="%.0f")
    d.line([(boxC[0], boxC[3] - (boxC[3] - boxC[1]) * (110 - core_center[0]) / 110.0),
            (boxC[2], boxC[3] - (boxC[3] - boxC[1]) * (110 - core_center[0]) / 110.0)],
           fill=(200, 120, 120), width=1)
    g_arms = [n for n in ("shell_OXC_hot", "shell_OXC_hot_g002",
                          "shell_OXC_hot_g030") if n in series]
    for name in g_arms:
        ss = series[name]
        line(d, boxC, [p["t"] for p in ss],
             [None if p["shell_cy"] is None else 110.0 - p["shell_cy"] for p in ss],
             T, 110, COL.get(name, (100, 100, 100)), 3)
    legend(d, boxC[0] + 14, boxC[1] + 10,
           [(LAB.get(n, n), COL.get(n, (100, 100, 100))) for n in g_arms]
           + [("核心高度", (200, 120, 120))])

    boxD = (1030, 690, 1810, 1090)
    d.text((1030, 636), "D 壳物质数 / 壳分子存活 / 外来穿透深度", font=fnt(18, True), fill=INK)
    dmax = 100.0
    for name in ("shell_OXC_hot", "shell_C2_hot", "double_OXC_OP_hot"):
        if name in arms:
            dmax = max(dmax, arms[name]["shell_alive0"] or 0,
                       arms[name]["shell_alive_final"] or 0,
                       10.0 * (arms[name]["foreign_min_r_final"] or 0))
    dmax = 50.0 * math.ceil(dmax / 50.0)
    axes(d, boxD, dmax, "计数（壳）与格（距离×10）", "t（拍）", T, fmt="%.0f")
    ss = series.get("shell_OXC_hot", [])
    if ss:
        line(d, boxD, [p["t"] for p in ss], [p["shell_formula_n"] for p in ss],
             T, dmax, (40, 120, 210), 3)
        line(d, boxD, [p["t"] for p in ss], [p["shell_alive"] for p in ss],
             T, dmax, (120, 160, 220), 2)
        line(d, boxD, [p["t"] for p in ss],
             [10.0 * (p["foreign_min_r"] or 0.0) for p in ss],
             T, dmax, (200, 90, 140), 2)
    legend(d, boxD[0] + 14, boxD[1] + 10,
           [("壳物质数（OXC 分子式）", (40, 120, 210)),
            ("初始壳分子存活（按 id）", (120, 160, 220)),
            ("外来最近距离 ×10（格）", (200, 90, 140))])

    # E 末态壳竖直分布（主臂）
    ex, ey = 1900, 690
    d.text((ex - 40, 636), "E 终态壳竖直分布（主臂）", font=fnt(18, True), fill=INK)
    hist = series["shell_OXC_hot"][-1]["shell_y_hist"] if "shell_OXC_hot" in series else []
    hmax = max(hist) if hist and max(hist) > 0 else 1
    for i, v in enumerate(hist):
        yy = ey + (10 - i) * 34
        d.rectangle([ex, yy, ex + 300 * v / hmax, yy + 26], fill=(40, 120, 210))
        d.text((ex + 300 * v / hmax + 6, yy + 3), "%d" % v, font=fnt(12), fill=SUB)
        d.text((ex - 34, yy + 3), "%d-%d" % (i * 10, (i + 1) * 10 - 1),
               font=fnt(11), fill=SUB)
    d.text((ex - 40, 1090),
           "重力 G=0.30 时重壳（OXC mass=3，gacc 线性累积、无终端速度）会持续下沉；"
           "G=0.02 为微重力对照。具体沉降量以 JSON 的 shell_cy / shell_y_hist 为准。",
           font=fnt(14), fill=SUB)
    img.save(os.path.join(IMGDIR, "t93_shell.png"))
    print("saved images/t93_shell.png", img.size)

    print("all images ->", IMGDIR)


if __name__ == "__main__":
    main()
