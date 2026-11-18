# -*- coding: utf-8 -*-
"""T76 桥的功用标签页。"""
from collections import Counter

import t68_shapes as S
import t69_pieces as P
import t75_tiles as T
import t76_bridge_fn as F

INK = (38, 50, 64)
INK2 = (104, 120, 136)
FCOL = {
    "weld": (0xC0, 0x39, 0x2B), "anchor": (0x8E, 0x2B, 0x1E),
    "hinge": (0x1E, 0x84, 0x49), "tendon": (0x27, 0xAE, 0x60), "cable": (0x16, 0xA0, 0x85),
    "gap": (0x2E, 0x86, 0xC1), "buffer": (0x1A, 0xBC, 0x9C), "insulate": (0x5D, 0xAD, 0xE2),
    "rigidflex": (0x8E, 0x44, 0xAD), "damper": (0x6C, 0x34, 0x83),
    "braid": (0xD3, 0x54, 0x00), "bundle": (0x2C, 0x3E, 0x50), "spacer": (0xB9, 0x77, 0x0E),
}
DEMO = {
    "weld": ["X"], "anchor": ["XX"], "hinge": ["W"], "tendon": ["WW"], "cable": ["WWW"],
    "gap": ["A"], "buffer": ["AA"], "insulate": ["AAA"], "rigidflex": ["XW"],
    "damper": ["WA"], "braid": ["XWA"], "spacer": ["XA"],
}


def _wrap_txt(cv, x, y, text, size, maxw):
    line, yy = "", y
    for ch in text:
        t = line + ch
        if cv.f(size).getlength(t) > maxw and line:
            cv.txt(x, yy, line, size, False, INK2, "la")
            line, yy = ch, yy + int(size * 1.5)
        else:
            line = t
    if line:
        cv.txt(x, yy, line, size, False, INK2, "la")
    return yy


def page(path="images/t76_bridge_functions.png"):
    mols = P.load_data()["molecules"]
    st = F.stats(mols)
    cv = S.Canvas(1600, 1330, (255, 255, 255))
    cv.txt(40, 46, "T76 桥的功用标签：桥只负责“连”，但不同连法功能不同", 26, True, INK, "lm")
    cv.txt(40, 78, "连接两个骨架的二价桥不参与属性计算，但它是功能件：晶 X=刚件、流 W=柔件、气 A=空腔；"
                   "单段/双段/长链与混编顺序决定它干的活。", 12.3, False, INK2, "lm")

    # A 判定表
    cv.txt(40, 126, "A. 判定规则：元素角色 × 段数 × 混编方式", 16, True, INK, "lm")
    rows = [
        ("晶 X", "刚件", "X → 刚性焊接；XX → 承重锚固"),
        ("流 W", "柔件", "W → 铰接关节；WW → 可伸缩肌腱；WWW+ → 牵拉缆索"),
        ("气 A", "空腔", "A → 隔空软连；AA → 缓冲气囊；AAA+ → 隔热隔振"),
        ("刚 + 空", "定距", "XA / XXA / XAA → 定距隔空（刚性件把间距锁住，空腔不传热振）"),
        ("刚 + 柔", "复合", "XW / XXW → 刚柔复合（一端锁死一端可弯）"),
        ("柔 + 空", "软索", "WA → 隔振软索；WAA → 缓冲软索"),
        ("三元素", "编织", "XWA / XWAA / XXWA → 多点编织（不同段分担载荷、保留柔性）"),
    ]
    y = 164
    for a, b, c in rows:
        cv.txt(70, y, a, 12, True, INK, "lm")
        cv.txt(200, y, b, 12, True, (0x1E, 0x84, 0x49), "lm")
        cv.txt(280, y, c, 11.5, False, INK2, "lm")
        y += 26

    # B 功能图例
    cv.txt(40, 372, "B. 功能标签（每种给一个真实桥的连法示意）", 16, True, INK, "lm")
    order = ["weld", "anchor", "hinge", "tendon", "cable", "gap", "buffer", "insulate",
             "spacer", "rigidflex", "damper", "braid"]
    for i, key in enumerate(order):
        col = i % 6
        row = i // 6
        x = 60 + col * 254
        y2 = 412 + row * 250
        cv.d.rounded_rectangle([x, y2, x + 238, y2 + 224], radius=10, fill=(252, 253, 255),
                               outline=(228, 234, 240))
        # 两个小方块 + 桥
        bx, by, s2 = x + 30, y2 + 48, 78
        cv.d.rectangle([bx, by, bx + s2, by + s2], fill=(244, 248, 251), outline=(178, 190, 202))
        cv.d.rectangle([bx + s2, by, bx + 2 * s2, by + s2], fill=(244, 248, 251), outline=(178, 190, 202))
        T.draw_bridge_on_edge(cv, bx + s2, by + s2 / 2, s2, "v", DEMO[key])
        zh, code, desc = F.FUNCS[key]
        c = FCOL.get(key, INK)
        cv.txt(x + 18, y2 + 20, zh, 14, True, c, "lm")
        cv.txt(x + 130, y2 + 20, "×%d" % st.get(key, 0), 12, True, INK2, "lm")
        _wrap_txt(cv, x + 18, y2 + 150, desc, 9.6, 200)
        cv.txt(x + 18, y2 + 206, "例：" + "-".join(DEMO[key]), 9.2, False, (140, 154, 168), "lm")

    # C 统计（逐行条形，小项也能读）
    cv.txt(40, 918, "C. 36 个大分子里的 114 条桥：功能分布（同一对骨架之间多根并联时另记“并联×n”）", 16, True, INK, "lm")
    total = sum(st.values()) or 1
    x0, yy = 80, 950
    n_par = sum(1 for m in mols for b2 in F.all_bridges(m) if b2.get("par", 1) > 1)
    for key in order:
        n = st.get(key, 0)
        if not n:
            continue
        col = FCOL.get(key, INK)
        cv.txt(x0, yy, F.FUNCS[key][0], 10.5, True, col, "lm")
        cv.d.rounded_rectangle([x0 + 92, yy - 7, x0 + 92 + 420, yy + 7], radius=7,
                               fill=(244, 247, 250), outline=(232, 238, 244))
        w = max(4, int(420 * n / total))
        cv.d.rounded_rectangle([x0 + 92, yy - 7, x0 + 92 + w, yy + 7], radius=7, fill=col)
        cv.txt(x0 + 522, yy, "%d 条 · %d%%" % (n, round(100.0 * n / total)), 10, False, INK2, "lm")
        yy += 22
    cv.txt(x0 + 700, 950, "其中“并联”桥 %d 条（同对骨架 ≥2 根并行）" % n_par, 10, False, INK2, "lm")
    cv.txt(x0 + 700, 974, "桥的元件只做功能：不参与硬度/粘性/温度计算。", 10, False, INK2, "lm")

    # D 例子
    by = {m["mid"]: m for m in mols}
    cv.txt(40, 1196, "D. 例子：G13 的 7 条桥（4 X + 3 W，分布在 4 块骨架之间）", 14, True, INK, "lm")
    parts = []
    for b in F.all_bridges(by["G13"]):
        parts.append("桥%d %s→%s%s" % (b["bid"] + 1, b["elems"], b["fn_zh"],
                                      "×%d" % b["par"] if b.get("par", 1) > 1 else ""))
    cv.txt(40, 1226, "   ".join(parts), 10.4, False, INK2, "lm")
    cv.txt(40, 1260, "G16 的桥：X→刚性焊接 ×2；W-A-A→多点编织 ×2（气段留空、流段可弯，合起来是柔性长连接）。",
           10.4, False, INK2, "lm")
    cv.save(path)
    print("saved", path)


if __name__ == "__main__":
    page()
