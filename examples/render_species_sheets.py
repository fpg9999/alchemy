# -*- coding: utf-8 -*-
"""渲染五个候选群系的物质结构图（六边形棋盘格）。

只取**目录内（≤16 原子、已验证）**的 46 种物质——它们是当前的命名对象。
视觉语言沿用项目既有约定（t61/t62/t63 的六边形棋盘格）：

    占据格 = 原子（按元素上色 + 元素字母）
    键型   = S 红（共享边）/ C 绿（共享顶点）/ L 紫（隔一格长键）
    多重键 = 平行线条数
    L 中点 = 紫虚线格，必须为空
    灰细线 = 棋盘格空位（分子外围一圈）

产出（images/biome_candidates/）：
    species_01.png … species_0N.png   结构图分页（每页 12 个）
    species_index.png                 索引表（含 5 个群系的丰度）
    species_legend.png                图例

运行（仓库根）：
    python examples/render_species_sheets.py
"""

import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import alchemy  # noqa: E402
import alchemy.phase as PH  # noqa: E402
from alchemy.core.elements import CN, ORDER, classify_offset  # noqa: E402

UNION = REPO / "data" / "biomes" / "candidates" / "_union.json"
OUT_DIR = REPO / "images" / "biome_candidates"

S3 = math.sqrt(3.0)

# 与项目既有图一致的配色
# 配色以设计稿（元素周期图）为准：中心恒素 + 三辐条（聚/散/动）+ 三层环（1/2/3 价）
ELEMCOL = {"O": "#46B95B",   # 秩 绿
           "X": "#F5A623",   # 晶 橙
           "C": "#3FD0C9",   # 冰 青
           "P": "#F07AC8",   # 势 品红
           "W": "#3B6FD4",   # 流 蓝
           "L": "#F5E04B",   # 电 黄
           "K": "#8E5AA8",   # 沌 紫
           "A": "#B3B3B3",   # 气 灰
           "F": "#E74C3C"}   # 焰 红
LIGHT_TEXT = {"P", "K", "F", "W"}
BONDCOL = {"S": "#c0392b", "C": "#1e8449", "L": "#8e44ad", None: "#7f8c8d"}
BONDNAME = {"S": "S 共享边", "C": "C 共享顶点", "L": "L 隔格长键", None: "未解析"}
GRIDCOL = "#e2e2e2"
MIDCOL = "#8e44ad"

TAGS = ["T55", "T57", "T63S4", "T62B", "T59B"]
TAG_DESC = {
    "T55": "纯聚素", "T57": "29聚素", "T63S4": "K滴定",
    "T62B": "等量价数", "T59B": "三价最多",
}


# ---------------------------------------------------------------- 字体
def _font(size, bold=False):
    for path, index in (
        ("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc", 0),
        ("C:/Windows/Fonts/simhei.ttf", 0),
        ("C:/Windows/Fonts/segoeui.ttf", 0),
    ):
        try:
            return ImageFont.truetype(path, size, index=index)
        except Exception:
            continue
    return ImageFont.load_default()


class _FontDict(dict):
    """按字号惰性加载字体（F[13] 这样用，缺哪个字号就临时加载哪个）。"""

    def __init__(self, bold):
        super().__init__()
        self.bold = bold

    def __missing__(self, size):
        f = _font(size, self.bold)
        self[size] = f
        return f


F = _FontDict(False)
FB = _FontDict(True)


# ---------------------------------------------------------------- 几何
def center_of(cell, s):
    q, r = cell
    return (1.5 * s * q, S3 * s * (r + q / 2.0))


def hex_pts(cx, cy, s):
    return [(cx + s * math.cos(math.radians(60 * i)),
             cy + s * math.sin(math.radians(60 * i))) for i in range(6)]


def dashed(draw, p0, p1, fill, width=1, dash=4, gap=3):
    x0, y0 = p0
    x1, y1 = p1
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 1e-6:
        return
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    t = 0.0
    while t < L:
        t2 = min(L, t + dash)
        draw.line([(x0 + ux * t, y0 + uy * t), (x0 + ux * t2, y0 + uy * t2)],
                  fill=fill, width=width)
        t = t2 + gap


def draw_bond(draw, p0, p1, typ, m):
    """键的视觉语法：

    - **颜色** = 键型（S 红 / C 绿 / L 紫）
    - **粗细** = 键级（1 级 2px / 2 级 5px / 3 级 8px）

    早期版本用"平行线条数"表示键级，但在小尺寸分子上（键段只有 4~6 像素长）
    双键与三键的平行线会糊成一团。改用粗细后，任何尺寸都能一眼分辨。
    """
    col = BONDCOL.get(typ, "#7f8c8d")
    m = max(1, int(m or 1))
    width = 3 + 2 * (m - 1)          # 1→3px  2→5px  3→7px
    draw.line([p0, p1], fill=col, width=width)


# ---------------------------------------------------------------- 单个分子面板
def panel(d, item, box, rank, font_scale=1.0):
    x0, y0, x1, y1 = box
    d.rectangle([x0, y0, x1, y1], fill="#ffffff", outline="#c8c8c8")
    formula = item["formula"]
    natoms = item["natoms"]
    label = item.get("_label") or ""
    shape = item.get("shape") or "?"
    blocks = item.get("skeleton_blocks") or ""
    props = item.get("props") or {}

    d.text((x0 + 8, y0 + 5), f"#{rank}  {formula}", font=FB[14], fill="#111")
    d.text((x0 + 8, y0 + 24), f"{label}", font=F[10], fill="#444")

    # 棋盘格区域
    ax0, ay0, ax1, ay1 = x0 + 6, y0 + 44, x1 - 6, y1 - 30
    place = [tuple(p) for p in item["_place"]]
    occ = set(place)
    edges = [tuple(e) for e in item["_edges"]]
    mids = set()
    bonds = []
    for (i, j, m) in edges:
        dq = place[j][0] - place[i][0]
        dr = place[j][1] - place[i][1]
        typ = classify_offset((dq, dr))
        bonds.append((i, j, m, typ))
        if typ == "L":
            mids.add(((place[i][0] + place[j][0]) // 2, (place[i][1] + place[j][1]) // 2))

    qs = [p[0] for p in place] + [m[0] for m in mids]
    rs = [p[1] for p in place] + [m[1] for m in mids]
    q0, q1, r0, r1 = min(qs) - 1, max(qs) + 1, min(rs) - 1, max(rs) + 1

    pts = [center_of((q, r), 1.0) for q in range(q0, q1 + 1) for r in range(r0, r1 + 1)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = min(xs) - 1.0, max(xs) + 1.0
    miny, maxy = min(ys) - S3 / 2.0 - 0.2, max(ys) + S3 / 2.0 + 0.2
    pad = 3
    s = min((ax1 - ax0 - 2 * pad) / max(1e-6, maxx - minx),
            (ay1 - ay0 - 2 * pad) / max(1e-6, maxy - miny))
    cx = ax0 + (ax1 - ax0) / 2.0 - (minx + maxx) / 2.0 * s
    cy = ay0 + (ay1 - ay0) / 2.0 - (miny + maxy) / 2.0 * s

    def C(cell):
        p = center_of(cell, s)
        return (cx + p[0], cy + p[1])

    # 1) 棋盘格空格
    for q in range(q0, q1 + 1):
        for r in range(r0, r1 + 1):
            cell = (q, r)
            if cell in occ:
                continue
            poly = hex_pts(*C(cell), s)
            if cell in mids:
                d.polygon(poly, fill="#f7f0fb")
                dashed(d, poly[0], poly[1], MIDCOL, 2)
                for k in range(6):
                    dashed(d, poly[k], poly[(k + 1) % 6], MIDCOL, 2)
            else:
                d.polygon(poly, outline=GRIDCOL, width=1)
    # 2) 键（先画键、再画原子：原子内缩到 0.82·s，键只在缝隙里露出
    #    L 长键画整段直线，靠紫色虚线中点格标示"隔一格"）
    for (i, j, m, typ) in bonds:
        draw_bond(d, C(place[i]), C(place[j]), typ, m)
    # 3) 原子（内缩 0.78：留出更长的键段，键级粗细才看得出来）
    RH = 0.78
    for i, cell in enumerate(place):
        el = item["_atoms"][i]
        poly = hex_pts(*C(cell), s * RH)
        d.polygon(poly, fill=ELEMCOL.get(el, "#bdbdbd"), outline="#222", width=2)
        if s >= 9:
            d.text(C(cell), el, font=FB[max(9, int(s * 0.8))],
                   fill="#ffffff" if el in LIGHT_TEXT else "#111", anchor="mm")

    # 4) 页脚：物性名（原"原子·形状·骨架 / 耐久·攻击"整段替换掉）
    de = PH.describe(formula)
    d.text((x0 + 8, y1 - 31), de["name"], font=FB[14], fill="#111")
    d.text((x0 + 8, y1 - 12), f"{de['id']}  ·  {de['typical']}", font=F[10], fill="#666")


# ---------------------------------------------------------------- 分页
def sheet_page(items, page, pages, path):
    W, H = 1600, 1240
    im = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(im)
    d.text((28, 20), f"候选群系的物质结构图（第 {page}/{pages} 页）", font=FB[24], fill="#111")
    d.text((28, 56),
           "占据格=原子（按元素上色）；键型按颜色区分：S 红（共享边）/ C 绿（共享顶点）/ L 紫（隔一格）；"
           "键级按粗细区分：1 级 / 2 级 / 3 级",
           font=F[12], fill="#555")
    d.text((28, 76),
           "紫虚线格 = L 键中点（必须为空）；灰细线 = 棋盘格空位。左下角为三轴合成的物性名",
           font=F[11], fill="#888")

    cols, rows = 4, 3
    pw, ph = 383, 330
    top = 104
    for i, item in enumerate(items):
        r, col = divmod(i, cols)
        x0 = 24 + col * (pw + 8)
        y0 = top + r * (ph + 8)
        panel(d, item, (x0, y0, x0 + pw, y0 + ph),
              rank=(page - 1) * cols * rows + i + 1)
    for i in range(len(items), cols * rows):
        r, col = divmod(i, cols)
        x0 = 24 + col * (pw + 8)
        y0 = top + r * (ph + 8)
        d.rectangle([x0, y0, x0 + pw, y0 + ph], outline="#f0f0f0")

    d.text((28, H - 34),
           "结构 = 目录 t4_catalog_all_validated.json 的 atoms/edges/place，"
           "经 pot_v2.validate_place 逐条复核通过；键型由 place 位移反推（S/C/L）。",
           font=F[11], fill="#666")
    im.save(path)
    return path


# ---------------------------------------------------------------- 索引页
def sheet_index(items, path):
    W = 1600
    row_h = 21
    H = 170 + len(items) * row_h + 70
    im = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(im)
    d.text((28, 20), f"候选群系物质索引（目录内 {len(items)} 种，按最高丰度排序）",
           font=FB[24], fill="#111")
    d.text((28, 58), "丰度 = 该物质在对应群系里占分子总数的比例；留空 = 该群系不出现",
           font=F[12], fill="#555")

    xs = [34, 74, 210, 430, 500, 560]
    heads = ["#", "分子式", "标识（机械）", "原子", "形状", "6级骨架块"]
    xs.append(770)
    heads.append("物性名")
    for t, x in zip(TAGS, [980, 1090, 1200, 1320, 1440]):
        xs.append(x)
        heads.append(t)
    for x, h in zip(xs, heads):
        d.text((x, 96), h, font=FB[11], fill="#111")
    d.line([30, 114, W - 22, 114], fill="#999", width=1)

    for i, item in enumerate(items):
        y = 120 + i * row_h
        vals = [str(i + 1), item["formula"], item.get("_label") or "",
                str(item["natoms"]), item.get("shape") or "",
                item.get("skeleton_blocks") or "—",
                PH.describe(item["formula"])["name"]]
        ab = item.get("abundance") or {}
        for t in TAGS:
            vals.append(f"{ab[t]:.3%}" if t in ab else "—")
        for j, (x, v) in enumerate(zip(xs, vals)):
            col = "#111"
            if j == 0:
                col = "#888"
            if j == 1:
                d.text((x, y), str(v), font=FB[10], fill="#111")
            else:
                d.text((x, y), str(v), font=F[10], fill=col)
        if i % 2 == 0:
            d.rectangle([30, y - 2, W - 22, y + row_h - 4], outline="#f4f4f4")

    d.text((28, H - 40),
           "群系说明：T55 纯聚素碰撞 / T57 29 种聚素 / T63S4 逐级价数滴定(K阶段) / "
           "T62B 九元素等量价数 / T59B 九元素三价最多",
           font=F[11], fill="#666")
    im.save(path)
    return path


# ---------------------------------------------------------------- 图例
def sheet_legend(path):
    W, H = 1600, 900
    im = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(im)
    d.text((28, 20), "图例：元素配色 / 三种键型 / 多重键 / L 中点空格", font=FB[24], fill="#111")
    d.text((28, 58), "flat-top 六边形：center = (1.5·s·q, √3·s·(r + q/2))",
           font=F[12], fill="#555")

    d.text((36, 110), "① 9 种元素（六边形=原子，字母=元素，中文=单字名）",
           font=FB[16], fill="#111")
    x = 70
    for e in ORDER:
        poly = hex_pts(x, 200, 28)
        d.polygon(poly, fill=ELEMCOL[e], outline="#222", width=2)
        d.text((x, 200), e, font=FB[18], fill="#ffffff" if e in LIGHT_TEXT else "#111",
               anchor="mm")
        d.text((x, 246), f"{e} {CN[e]}", font=F[13], fill="#333", anchor="ma")
        x += 118

    d.text((36, 300), "② 键型看颜色（S 红 / C 绿 / L 紫），键级看粗细（1 级最细、3 级最粗）",
           font=FB[16], fill="#111")
    demo = [("S", 1), ("S", 2), ("S", 3), ("C", 1), ("L", 1), ("L", 2)]
    x = 80
    for typ, m in demo:
        p0, p1 = (x, 400), (x + 120, 400)
        draw_bond(d, p0, p1, typ, m)
        d.polygon(hex_pts(x, 400, 17), fill="#dddddd", outline="#333")
        d.polygon(hex_pts(x + 120, 400, 17), fill="#dddddd", outline="#333")
        if typ == "L":
            mid = ((p0[0] + p1[0]) / 2.0, 400)
            poly = hex_pts(mid[0], mid[1], 17)
            d.polygon(poly, fill="#f7f0fb")
            for k in range(6):
                dashed(d, poly[k], poly[(k + 1) % 6], MIDCOL, 2)
            d.text((mid[0], mid[1] + 30), "中点必须为空", font=F[10], fill=MIDCOL,
                   anchor="ma")
        d.text((x + 60, 450), f"{BONDNAME.get(typ, '')} · 键级 {m}", font=F[11],
               fill="#333", anchor="ma")
        x += 250

    d.text((36, 520), "③ 怎么读一个面板", font=FB[16], fill="#111")
    lines = [
        "标题行：序号 + 分子式（与目录、物种表的主键一致）",
        "第二行：机械标识 = 元素中文串 + 结构后缀（如 秩晶冰·链），不是游戏名",
        "棋盘：实心六边形 = 原子；周围的浅灰细线 = 棋盘格空位（体现网格）",
        "紫虚线格 = 长键 L 的中间格，按规则必须为空",
        "页脚：原子数 · 形状（团/星/环/链/孤核）· 6 级骨架块 · 耐久/攻击",
    ]
    for i, t in enumerate(lines):
        d.text((56, 556 + i * 26), "· " + t, font=F[13], fill="#333")

    d.text((36, 720), "④ 元素 → 键型倾向（为什么 S/C/L 与元素绑定）", font=FB[16], fill="#111")
    rows = [("聚素 O/X/C", "S 短键（共享边）", "刚性，贴边"),
            ("动素 P/W/L", "C 角键（共享顶点）", "铰接，可转动"),
            ("散素 K/A/F", "L 长键（隔一格）", "柔性，长距离")]
    for i, (a, b_, c_) in enumerate(rows):
        y = 758 + i * 26
        d.text((56, y), f"· {a}", font=F[13], fill="#333")
        d.text((300, y), b_, font=F[13], fill="#333")
        d.text((620, y), c_, font=F[13], fill="#777")
    d.text((36, 850),
           "跨类元素之间允许多种键型（取两者允许集合的并集），所以上表是「倾向」而非绝对。",
           font=F[11], fill="#888")
    im.save(path)
    return path


# ---------------------------------------------------------------- main
def load_items():
    data = json.loads(UNION.read_text(encoding="utf-8"))
    cat = alchemy.get_catalog()
    items = []
    for u in data["species"]:
        if not u["in_catalog"]:
            continue
        rec = cat[u["formula"]]
        place = {int(k): (int(v[0]), int(v[1])) for k, v in rec["place"].items()}
        atoms = list(rec["atoms"])
        edges = [tuple(e) for e in rec["edges"]]
        ok, msg = alchemy.validate(place, atoms, edges)
        if not ok:
            print(f"  [warn] {u['formula']} 摆放校验失败：{msg}")
        it = dict(u)
        it["_atoms"] = atoms
        it["_edges"] = edges
        it["_place"] = [place[i] for i in range(len(atoms))]
        it["_label"] = u["label"]
        items.append(it)
    items.sort(key=lambda x: -x["max_abundance"])
    return items


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    items = load_items()
    print(f"目录内物质 {len(items)} 种（按最高丰度排序）")

    per = 12
    pages = [items[i:i + per] for i in range(0, len(items), per)]
    made = []
    for pi, page in enumerate(pages, 1):
        p = sheet_page(page, pi, len(pages), OUT_DIR / f"species_{pi:02d}.png")
        made.append(p)
        print(f"  [ok] 第 {pi}/{len(pages)} 页（{len(page)} 个）-> {p.name}")
    made.append(sheet_index(items, OUT_DIR / "species_index.png"))
    print("  [ok] 索引页 -> species_index.png")
    made.append(sheet_legend(OUT_DIR / "species_legend.png"))
    print("  [ok] 图例 -> species_legend.png")
    print(f"\n输出目录: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
