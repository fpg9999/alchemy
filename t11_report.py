# -*- coding: utf-8 -*-
"""t11_report.py：二元反应报告生成（统计 + Markdown + 图）
数据：t11_binary_ju.json / t11_binary_none.json / t11_binary_cross.json
结构：substances.json（29 聚素）、t9_single_trivalent.json（175 无三价）
"""
import json
import math
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from PIL import Image, ImageDraw

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import t8_render_forms as R

BASE = r"G:\AI work\deepseek\work1\alchemy"
font = R.font
FONT = R.FONT
FONT_B = R.FONT_B
text_center = R.text_center
draw_formula = R.draw_formula
BONDC = {"S": "#c0392b", "C": "#1e8449", "L": "#6c3483"}
CN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电",
      "K": "沌", "A": "气", "F": "焰"}
FILL = {"O": (107, 191, 107), "X": (240, 160, 75), "C": (127, 182, 232),
        "P": (240, 130, 185), "W": (201, 162, 39), "L": (255, 224, 102),
        "K": (150, 110, 220), "A": (143, 214, 192), "F": (224, 90, 79)}


# ---------------- 数据 ----------------
def load():
    ju = json.load(open(BASE + r"\t11_binary_ju.json", encoding="utf-8"))
    none = [{"A": r[0], "B": r[1], "ok": r[2], "products": r[3]}
            for r in json.load(open(BASE + r"\t11_binary_none.json", encoding="utf-8"))]
    cross = [{"A": r[0], "B": r[1], "ok": r[2], "products": r[3]}
             for r in json.load(open(BASE + r"\t11_binary_cross.json", encoding="utf-8"))]
    sub = json.load(open(BASE + r"\substances.json", encoding="utf-8"))
    t9 = json.load(open(BASE + r"\t9_single_trivalent.json", encoding="utf-8"))
    struct = {}
    for d in sub:
        struct[d["formula"]] = {"atoms": d["atoms"], "edges": [tuple(e) for e in d["edges"]],
                                "place": {int(k): tuple(v) for k, v in d["place"].items()}}
    for r in t9["none"]:
        struct[r["formula"]] = {"atoms": r["atoms"], "edges": [tuple(e) for e in r["edges"]],
                                "place": {int(k): tuple(v) for k, v in r["place"].items()}}
    return ju, none, cross, struct


def outcomes(rows):
    ok = [r for r in rows if r["ok"]]
    fail = [r for r in rows if not r["ok"]]
    inert = [r for r in ok if sorted(r["products"]) == sorted([r["A"], r["B"]])]
    single = [r for r in ok if len(r["products"]) == 1]
    multi = [r for r in ok if len(r["products"]) > 1 and r not in inert]
    return ok, fail, inert, single, multi


# ---------------- 绘图 ----------------
def draw_mol(d, st, box, label=True):
    x0, y0, w, h = box
    atoms = st["atoms"]
    edges = st["edges"]
    place = st["place"]
    n = len(atoms)
    s = 24.0
    for _ in range(60):
        pts = [R.center_of(place[i], s) for i in range(n)]
        if (max(p[0] for p in pts) - min(p[0] for p in pts) + 2.4 * s) <= w and \
           (max(p[1] for p in pts) - min(p[1] for p in pts) + 2.4 * s) <= h:
            break
        s *= 0.93
    pts = [R.center_of(place[i], s) for i in range(n)]
    ox = x0 + w / 2 - (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
    oy = y0 + h / 2 - (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    pos = [(p[0] + ox, p[1] + oy) for p in pts]
    polys = [R.hex_pts(pos[i][0], pos[i][1], s) for i in range(n)]
    for (i, j, m) in edges:
        dd = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        t = R.rel_type(dd)
        col = BONDC.get(t, "#333")
        width = max(2, int(s / 13)) if t in ("S", "C") else max(2, int(s / 16))
        if t == "S":
            sv = R.common_vertices(polys[i], polys[j])
            if len(sv) >= 2:
                R.ray_offset_line(d, sv[0], sv[1], col, width, m)
        elif t == "C":
            p1, p2 = R.nearest_vertices(polys[i], polys[j])
            R.ray_offset_line(d, p1, p2, col, width, m)
        elif t == "L":
            p1 = R.ray_exit(polys[i], pos[i], pos[j])
            p2 = R.ray_exit(polys[j], pos[j], pos[i])
            if p1 and p2:
                ux, uy = p2[0] - p1[0], p2[1] - p1[1]
                L = math.hypot(ux, uy)
                nx, ny = -uy / L, ux / L
                for k in range(m):
                    off = (k - (m - 1) / 2) * 5
                    a = (p1[0] + nx * off, p1[1] + ny * off)
                    b = (p2[0] + nx * off, p2[1] + ny * off)
                    R.dashed(d, a, b, col, width)
    for i, e in enumerate(atoms):
        d.polygon(polys[i], fill=FILL[e], outline="#333", width=max(1, int(s / 22)))
        text_center(d, pos[i][0], pos[i][1] - s * 0.14, e, font(FONT_B, int(s * 0.52)), "#111")
        text_center(d, pos[i][0], pos[i][1] + s * 0.34, CN[e], font(FONT, int(s * 0.34)), "#111")


def card(path, title, reactants, products, note=""):
    W, H = 1320, 360
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((24, 14), title, font=font(FONT_B, 22), fill="#111")
    if note:
        d.text((24, 46), note, font=font(FONT, 15), fill="#666")
    y = 80
    n_r = len(reactants)
    x = 30
    bw = 210
    for k, (name, st) in enumerate(reactants):
        draw_mol(d, st, (x, y, bw, 210))
        draw_formula(d, x + bw / 2, y + 216, name, 20, "#111")
        x += bw
        if k < n_r - 1:
            text_center(d, x + 20, y + 100, "+", font(FONT_B, 34), "#111")
            x += 46
    text_center(d, x + 30, y + 100, "→", font(FONT_B, 36), "#111")
    x += 80
    for k, (name, st) in enumerate(products):
        draw_mol(d, st, (x, y, bw, 210))
        draw_formula(d, x + bw / 2, y + 216, name, 20, "#111")
        x += bw
        if k < len(products) - 1:
            text_center(d, x + 18, y + 100, "+", font(FONT_B, 30), "#111")
            x += 40
    img.save(path)
    print("saved", path)


def matrix_ju(ju, path):
    names = sorted({r["A"] for r in ju} | {r["B"] for r in ju})
    idx = {n: i for i, n in enumerate(names)}
    n = len(names)
    cell = 26
    left, top = 130, 130
    W = left + n * cell + 30
    H = top + n * cell + 40
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 12), "29 种聚素物质 二元反应结果矩阵（上三角）", font=font(FONT_B, 22), fill="#111")
    d.text((20, 44), "行=第一个反应物，列=第二个反应物（行列顺序相同，见左侧名单）；灰=惰性 绿=单产物 橙=多产物 红=失败", font=font(FONT, 14), fill="#666")
    res = {}
    for r in ju:
        res[(r["A"], r["B"])] = r
    for a in range(n):
        d.text((left - 8, top + a * cell + 5), names[a], font=font(FONT, 12), fill="#333", anchor="rs")
        pass
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            if j < i:
                continue
            r = res.get((a, b)) or res.get((b, a))
            col = "#ffffff"
            if r is None:
                continue
            if not r["ok"]:
                col = "#d9534f"
            elif sorted(r["products"]) == sorted([a, b]):
                col = "#d9d9d9"
            elif len(r["products"]) == 1:
                col = "#6bbf6b"
            else:
                col = "#f0a04b"
            x0 = left + j * cell
            y0 = top + i * cell
            d.rectangle([x0, y0, x0 + cell - 2, y0 + cell - 2], fill=col, outline="#fff")
    img.save(path)
    print("saved", path)


def network_ju(ju, struct, path):
    """单产物反应的合成网络：x=原子数，y=物质"""
    singles = [r for r in ju if r["ok"] and len(r["products"]) == 1]
    names = sorted({r["A"] for r in singles} | {r["B"] for r in singles} |
                   {r["products"][0] for r in singles})
    natoms = {n: len(struct[n]["atoms"]) for n in names}
    groups = defaultdict(list)
    for n in names:
        groups[natoms[n]].append(n)
    W, H = 1500, 800
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 12), "聚素：单产物（化合）反应网络 —— 横轴=原子数，连线=A+B→C", font=font(FONT_B, 22), fill="#111")
    d.text((20, 44), "绿色点=反应物，红色点=产物；无单产物路径的 19 种物质不在此网络外（见报告）。", font=font(FONT, 14), fill="#666")
    xs = {k: 120 + (k - min(groups)) * (W - 220) / max(1, max(groups) - min(groups)) for k in groups}
    pos = {}
    for k, lst in groups.items():
        lst = sorted(lst)
        for i, n in enumerate(lst):
            y = 110 + (i + 0.5) * (H - 180) / len(lst)
            pos[n] = (xs[k], y)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for r in singles:
        a, b, c = r["A"], r["B"], r["products"][0]
        if a in pos and b in pos and c in pos:
            od.line([pos[a], pos[c]], fill=(120, 120, 200, 90), width=2)
            od.line([pos[b], pos[c]], fill=(120, 120, 200, 90), width=2)
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(img)
    prods = {r["products"][0] for r in singles}
    for n, (x, y) in pos.items():
        col = (200, 60, 60) if n in prods else (60, 140, 60)
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=col)
        d.text((x + 8, y - 7), n, font=font(FONT, 11), fill="#333")
    img.save(path)
    print("saved", path)


def bars(data, path):
    img = Image.new("RGB", (1100, 420), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 12), "二元反应结果统计", font=font(FONT_B, 22), fill="#111")
    labels = ["聚素29", "无三价175", "交叉29×175"]
    keys = ["inert", "single", "multi", "fail"]
    names = {"inert": "惰性", "single": "单产物", "multi": "多产物", "fail": "失败"}
    cols = {"inert": "#d9d9d9", "single": "#6bbf6b", "multi": "#f0a04b", "fail": "#d9534f"}
    maxv = max(max(v.values()) for v in data.values())
    bw = 90
    for gi, lab in enumerate(labels):
        x = 90 + gi * 330
        acc = 0
        y0, hh = 360, 280
        for k in keys:
            v = data[lab][k]
            bh = hh * v / maxv
            d.rectangle([x, y0 - acc - bh, x + bw, y0 - acc], fill=cols[k])
            if v > 0:
                text_center(d, x + bw / 2, y0 - acc - bh / 2, str(v), font(FONT_B, 13), "#111")
            acc += bh
        text_center(d, x + bw / 2, y0 + 18, lab, font(FONT, 15), "#333")
    # 图例
    x = 560
    for k in keys:
        d.rectangle([x, 390, x + 22, 412], fill=cols[k])
        d.text((x + 28, 392), names[k], font=font(FONT, 14), fill="#333")
        x += 110
    img.save(path)
    print("saved", path)




def cards_page(struct, path):
    """典型反应卡片（2×2）"""
    entries = [
        ("惰性：混合后原样返回", ["O2", "O2X2"], ["O2", "O2X2"], "O2 + O2X2 → 无净变化（反应重建了原分子）"),
        ("化合：单产物 = 向量加法", ["C2", "O2"], ["O2C2"], "C2 + O2 → O2C2（冰二聚 + 氧二聚 直接加成）"),
        ("复分解：归中/歧化", ["C2", "O2C4"], ["OC3", "OC3"], "C2 + O2C4 → 2 OC3（双键/价态重新分配）"),
        ("不相容：整锅失败", ["C2", "OXC"], [], "C2 + OXC → 失败（价数无法配平；两个稳定物质却不相容）"),
    ]
    pw, ph = 680, 380
    ncol, nrow = 2, 2
    img = Image.new("RGB", (ncol * pw + 20, nrow * ph + 20), "white")
    d = ImageDraw.Draw(img)
    for idx, (title, rs, ps, note) in enumerate(entries):
        r, c = divmod(idx, ncol)
        x0 = 10 + c * pw + 4
        y0 = 10 + r * ph + 4
        w, h = pw - 8, ph - 8
        d.rectangle([x0, y0, x0 + w, y0 + h], outline="#dddddd")
        d.text((x0 + 12, y0 + 8), title, font=font(FONT_B, 19), fill="#111")
        d.text((x0 + 12, y0 + 36), note, font=font(FONT, 13), fill="#666")
        y = y0 + 66
        x = x0 + 12
        bw = 150
        for k, nm in enumerate(rs):
            draw_mol(d, struct[nm], (x, y, bw, 190))
            draw_formula(d, x + bw / 2, y + 196, nm, 17, "#111")
            x += bw
            if k < len(rs) - 1:
                text_center(d, x + 14, y + 80, "+", font(FONT_B, 26), "#111")
                x += 32
        text_center(d, x + 22, y + 80, "→", font(FONT_B, 30), "#111")
        x += 56
        if not ps:
            text_center(d, x + 90, y + 80, "× 失败", font(FONT_B, 24), "#d9534f")
        else:
            for k, nm in enumerate(ps):
                draw_mol(d, struct[nm], (x, y, bw, 190))
                draw_formula(d, x + bw / 2, y + 196, nm, 17, "#111")
                x += bw
                if k < len(ps) - 1:
                    text_center(d, x + 14, y + 80, "+", font(FONT_B, 22), "#111")
                    x += 30
    img.save(path)
    print("saved", path)


# ---------------- 主流程 ----------------
def main():
    ju, none, cross, struct = load()
    j_ok, j_fail, j_inert, j_single, j_multi = outcomes(ju)
    n_ok, n_fail, n_inert, n_single, n_multi = outcomes(none)
    c_ok, c_fail, c_inert, c_single, c_multi = outcomes(cross)

    # 链：单产物反应的延长（DAG by 原子数）
    def chain_len(rows):
        # 每个物质的原子数
        natoms = {}
        for r in rows:
            for nm in [r["A"], r["B"]] + (r["products"] or []):
                if nm not in natoms:
                    natoms[nm] = sum(1 for _ in nm)
        edges = defaultdict(list)
        for r in rows:
            if r["ok"] and len(r["products"]) == 1:
                edges[(r["A"], r["B"])].append(r["products"][0])
                edges[(r["B"], r["A"])].append(r["products"][0])

        @lru_cache(maxsize=None)
        def f(a, b):
            best = 0
            for c in edges.get((a, b), ()):
                best = max(best, 1 + f(b, c))
            return best

        best = (0, None)
        for (a, b) in edges:
            v = f(a, b)
            if v > best[0]:
                best = (v, (a, b))
        # 展开链
        if best[1]:
            a, b = best[1]
            chain = [a, b]
            while True:
                nxt = None
                for c in edges.get((chain[-2], chain[-1]), ()):
                    if f(chain[-1], c) == f(chain[-2], chain[-1]) - 1:
                        nxt = c
                        break
                if nxt is None:
                    break
                chain.append(nxt)
            return best[0], chain
        return 0, None

    jlen, jchain = chain_len(ju)
    nlen, nchain = chain_len(none)
    clen, cchain = chain_len(cross)

    # 多产物模式统计
    def patterns(rows):
        cnt = Counter()
        sym = 0
        for r in rows:
            if not r["ok"] or len(r["products"]) <= 1:
                continue
            p = r["products"]
            if len(p) == 2 and p[0] == p[1]:
                cnt["2×同种"] += 1
            elif len(p) == 2:
                cnt["2×不同"] += 1
            elif len(p) == 3:
                from collections import Counter as C2
                cc = C2(p)
                if max(cc.values()) == 3:
                    cnt["3×同种"] += 1
                elif max(cc.values()) == 2:
                    cnt["1+2(含同种)"] += 1
                else:
                    cnt["3×不同"] += 1
            else:
                cnt[f"{len(p)}产物"] += 1
        return cnt

    # 物质画像
    prof = defaultdict(Counter)
    for rows, tag in [(ju, "ju"), (none, "none"), (cross, "cross")]:
        for r in rows:
            for x, y in ((r["A"], r["B"]), (r["B"], r["A"])):
                if not r["ok"]:
                    prof[x]["fail"] += 1
                else:
                    p = r["products"]
                    if sorted(p) == sorted([x, y]):
                        prof[x]["inert"] += 1
                    elif len(p) == 1:
                        prof[x]["single"] += 1
                    else:
                        prof[x]["multi"] += 1

    # 报告
    L = []
    A = L.append
    A("# T11 · 两个物质之间的反应（二元反应）研究报告\n")
    A("> 生成时间：2026-11-13；目录：`G:\\AI work\\deepseek\\work1\\alchemy`\n")
    A("## 0. 前期成果总结（结构研究）\n")
    A("- 规则体系：9 元素（聚/动/散 × 3/2/1 价）、三种键（短键S/角键C/长键L）、规则 1~8 的确定性格子反应；")
    A("  产物必须每原子键数=价数、连通、可在六边形格上摆放。\n")
    A("- 聚素：29 种物质（含 3 单质、最大 9 原子），图 `final_all_29.png`。\n")
    A("- 三价元素 6 级结合：**38 种骨架形态库**（两/三种三价元素共存），最大组件 13 原子、活跃 ≤7；")
    A("  更大规模验证 = 只复制不新生（`T8_TRIVALENT_FORMS.md`）。\n")
    A("- 只含一种三价元素的物质 7,814 种：骨架 = **7 种模块的不交并**（单原子/二聚体1·2·3键/三元链/三元环），")
    A("  连通块 ≤3 原子（`T10_SKELETONS.md`）。\n")
    A("- 不含三价元素的物质 175 种，全部 ≤7 原子，结构 = 二聚体 / 纯2价小环 / 双端帽链（`T9_NONE_ALL.md`）。\n")
    A("- 目录：`t4_catalog_all_validated.json`（84,225 条）；511 类全部有限。\n")

    A("## 1. 二元反应的定义与口径\n")
    A("把物质 A、B 一起投锅（恒素触媒忽略）：全部原子拆开，按规则 1~8 逐根成键；")
    A("反应成功 = 所有原子价数填满且每个产物分子能合法摆放。产物为分子式多重集（可为 1 个、2 个或多个）。\n")
    A("**关键性质：反应结果只取决于「元素计数向量之和」 vA+vB**（与原来是什么分子无关）。\n")

    A("## 2. 基本定律（由定义直接推得，且数据全部验证）\n")
    A("1. **可交换**：R(A,B)=R(B,A)。\n")
    A("2. **总向量决定一切**：vA+vB 相同 ⇒ 反应结果完全相同。")
    A("   例（无三价内部）：`A2+W2` 与 `WA+WA` 总向量都是 2W+2A，结果都是 `2 WA`；`A2+X2` 与 `XA+XA` → `2 XA`。\n")
    A("3. **单产物 = 严格向量加法**：A+B→C 当且仅当 vA+vB 恰好等于某个物质 C 的向量；此时产物就是 C。")
    A("   推论：**不存在催化/取代**（A+B→A+C 会要求 vC=vB ⇒ C=B），也不存在「单向转化」。\n")
    A("4. **不存在反应循环**：若 A+B→C（单产物）则 vC=vA+vB（向量严格变大）；")
    A("   多产物步总向量不变，而结果由总向量唯一决定 ⇒ 任何闭环的最后一步必须与第一步产物相同，")
    A("   即整条环只能是「惰性步」（产物=反应物）。所以「A+B→C，C+D→A」型循环**不可能存在**（数学上被守恒+确定性排除）。\n")
    A("5. **失败=不相容**：两个各自合法的物质混合后，可能因价数无法配平而整锅失败（聚素内 3 对；交叉 129 对）。\n")
    A("6. **反应等价类**：把投料对按总向量分组，同一组结果必相同；这是给「反应性质」分类的自然坐标。\n")

    # 统计表
    A("## 3. 统计总览\n")
    A("| 反应集合 | 对数 | 成功 | 失败 | 惰性 | 单产物 | 多产物 |")
    A("|---|---|---|---|---|---|---|")
    A(f"| 聚素 29 内部 | {len(ju)} | {len(j_ok)} | {len(j_fail)} | {len(j_inert)} | {len(j_single)} | {len(j_multi)} |")
    A(f"| 无三价 175 内部 | {len(none)} | {len(n_ok)} | {len(n_fail)} | {len(n_inert)} | {len(n_single)} | {len(n_multi)} |")
    A(f"| 交叉 29×175 | {len(cross)} | {len(c_ok)} | {len(c_fail)} | {len(c_inert)} | {len(c_single)} | {len(c_multi)} |")
    A("")
    A(f"- 聚素 失败对：{[(r['A'], r['B']) for r in j_fail]}")
    A(f"- 最长单产物增长链：聚素 {jlen} 步 {jchain}；无三价 {nlen} 步 {nchain}；交叉 {clen} 步 {cchain}")
    A(f"- 多产物模式：聚素 {dict(patterns(ju))}")
    A(f"  ；无三价 {dict(patterns(none))}")
    A(f"  ；交叉 {dict(patterns(cross))}\n")

    A("## 4. 聚素 29 的全部二元反应结果\n")
    A("完整表：`t11_binary_ju.json`。要点：\n")
    A("- **惰性对（原样返回）87 个**，如：`O2+O2`、`C2+O2C4`、`X2+X3`、`O2C2+O2X2` 等 → 混合不反应。")
    A("- **单产物（化合）40 个**，全部是严格向量加法，例如：")
    A("  `C2+O2→O2C2`、`O2+X2→O2X2`、`O2+X3→O2X3`、`O2X4+X3→O2X7`、`OC3+OX3C→O2X3C4`。")
    A("- **多产物（复分解）305 个**，典型模式：")
    A("  - 归中/对称歧化：`C2+O2C4→2 OC3`、`O2+O2X2→2 O2X`、`C2+O2X2→2 OXC`、`O2C4+X2→?`…")
    A("  - 交换重组：`C2+O3C5→O2C4+OC3`、`C2+OX2C→OC3+X2`、`O2+O2X3→O2X+O2X2`。")
    A("- **失败（不相容）3 对**：`C2+OXC`、`C2+O2XC4`、`O2C4+XC2` → 混合后价数配不平，整锅失败。\n")

    A("## 5. 无三价 175 内部 与 交叉 29×175\n")
    A("- 无三价 175 内部：15,400 对**全部成功**，没有失败（只有 2价/1价，价数总能配平）；")
    A("  惰性 1,473、单产物 449、多产物 13,478。多产物远多于聚素，说明「复分解」在无三价体系非常常见。")
    A("- 交叉 29×175：5,075 对，成功 4,946、**失败 129**（全部涉及含 O 的聚素物质，O 三价 + 低阶元素配比失衡）；")
    A("  惰性 97、单产物 604、多产物 4,245。")
    A("- 等价类现象非常明显：无三价内部 3,439 个不同总向量中 3,043 个类含多对（同一总组成不同分子对 → 结果相同）；")
    A("  交叉部分 3,158 类中 1,460 类含多对。这验证了「总向量决定一切」。\n")

    A("## 6. 反应性质独特的物质（专题）\n")
    def top(key, k=8):
        return [(s, c) for s, c in sorted(prof.items(), key=lambda kv: -kv[1][key])[:k]]
    A("### ① 惰性王：C2、L2、X2C2、X2")
    A("- `C2`（冰₂）：与 70 个伙伴混合后完全不变（惰性最多），但也能与 50 个伙伴化合、2 个伙伴不相容。")
    A("- `L2`（电₂）：惰性 57；`X2C2`（晶₂冰₂）惰性 54 且几乎不参与单产物（仅 8），是多产物型「反应惰性体」。")
    A("- `X2`（晶₂）：惰性 48，但单产物 77（最多）——既是惰性对象又是「化合枢纽」。")
    A("### ② 不相容王：O3XC（秩₃晶冰）")
    A(f"- `O3XC` 失败 26 次（最多），单产物 38、多产物 111、惰性 0：它几乎不与其它物质「和平共处」，")
    A("  混合时经常整锅失败或强制重组。")
    A("- `O2X`（秩₂晶）失败 16、单产物 47；`O3XC3` 失败 16；`O2` 失败 15。O 的存在显著提高「不相容」概率。")
    A("### ③ 化合枢纽：O2、X2、XA、OX3C")
    A("- `O2`：单产物 69（与含 X/C 的物质大量加成），失败 15，惰性 0：非常「活泼」。")
    A("- `X2`：单产物 77 为全库最高：`X2 + 任意含 X/C 物质` 常直接生成对应多一个 X 的化合物。")
    A("- `OX3C`：单产物 53、失败 0：是「温和加成剂」。\n")
    A("### ④ 连续反应：增长链与合成网络")
    A(f"- 无三价内部最长单产物增长链 {nlen} 步：{nchain}")
    A(f"- 交叉最长链 {clen} 步：{cchain}")
    A(f"- 聚素最长链仅 {jlen} 步：{jchain}（说明聚素的「化合增长」很快被惰性/复分解截断）。")
    A("- 从单质出发，聚素只有 8 种能靠单产物化合合成（O2C2、O2X2、X2C2、O2C4、O2X4、O2X6、O2X2C4 等），")
    A("  其余 19 种必须通过复分解/多步反应得到。\n")

    A("## 7. 文件与图\n")
    A("- 数据：`t11_binary_ju.json`（435 对）、`t11_binary_none.json`（15,400 对）、`t11_binary_cross.json`（5,075 对）。")
    A("- 脚本：`t11_reactions.py`（反应计算）、`t11_analyze.py`、`t11_chains.py`、`t11_binary_more.py`、`t11_report.py`。")
    A("- 图：`t11_matrix_ju.png`（29×29 结果矩阵）、`t11_network_ju.png`（单产物合成网络）、`t11_bars.png`（统计）、`t11_cards.png`（典型反应卡片）。")

    open(BASE + r"\T11_BINARY_REACTIONS.md", "w", encoding="utf-8").write("\n".join(L))
    print("saved T11_BINARY_REACTIONS.md")

    # 图
    matrix_ju(ju, BASE + r"\t11_matrix_ju.png")
    network_ju(ju, struct, BASE + r"\t11_network_ju.png")
    bars({"聚素29": {"inert": len(j_inert), "single": len(j_single), "multi": len(j_multi), "fail": len(j_fail)},
          "无三价175": {"inert": len(n_inert), "single": len(n_single), "multi": len(n_multi), "fail": len(n_fail)},
          "交叉29×175": {"inert": len(c_inert), "single": len(c_single), "multi": len(c_multi), "fail": len(c_fail)}},
         BASE + r"\t11_bars.png")
    cards_page(struct, BASE + r"\t11_cards.png")


if __name__ == "__main__":
    main()
