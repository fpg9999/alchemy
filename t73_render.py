# -*- coding: utf-8 -*-
"""T73 图：① 器官形态几何判定规则；② 分化后的整体形体（形态长在体表）。"""
import t68_shapes as S
import t69_pieces as P
import t70b_body as BODY
import t73_body as T73B
import t72_abilities as AB
import t72_render as R2
import t72_morphs as M

INK = (40, 52, 66)
INK2 = (100, 116, 132)
W, H = 1600, 1440

MZH = {}
MTAGS = {}
for _fam, _lst in M.MORPHS.items():
    for _e in _lst:
        MZH[_e[0]] = _e[1]
        MTAGS[_e[0]] = _e[3]

KIND_COL = {"承力型": (0x8e, 0x44, 0xad), "感受/抓握型": (0x1e, 0x84, 0x49),
            "表面型": (0x16, 0xa0, 0x85), "内脏型": (0x2c, 0x3e, 0x50),
            "过渡型": (0xd3, 0x54, 0x00)}

PICKS = ["G13", "G14", "G16", "G23", "G24", "G33"]


def _morph_icon(cv, cx, cy, key, fam, w):
    tmp = S.Canvas(int(w + 40), int(w + 40), (255, 255, 255))
    M.draw_morph(tmp, tmp.W / 2.0, tmp.H / 2.0, w, w, key, fam)
    cv.img.paste(tmp.img, (int(cx - tmp.W / 2.0), int(cy - tmp.H / 2.0)))


def page_rules(path="images/t73_rules.png"):
    cv = S.Canvas(W, 780, (255, 255, 255))
    cv.txt(40, 46, "T73 器官形态的几何判定：器官长在什么位置，就长成什么形态", 26, True, INK, "lm")
    cv.txt(40, 78, "同一个骨架块，位置不同 → 形态不同：被桥拉住的长承力柱/腔，朝外张开的吸盘，铺在表面的鳞甲，藏在里面的格子。",
           12.5, False, INK2, "lm")
    rows = [
        ("承力型", "load ≥ 2（挂 ≥2 桥，或带融合）", KIND_COL["承力型"], "column", "OPK", "晶柱 / 主控腔：加厚承力，朝桥的方向伸"),
        ("感受/抓握型", "在身体外缘 + 至少有 1 根触肢/端帽", KIND_COL["感受/抓握型"], "sucker", "OP", "吸盘 / 神经节：朝外张开的感受面"),
        ("表面型", "在身体外缘，但没有触肢", KIND_COL["表面型"], "scale", "OK", "鳞片 / 盾甲：铺在体表的一层"),
        ("内脏型", "被包在里面（exposure ≤ 0.4）", KIND_COL["内脏型"], "frame", "O", "晶格框 / 储腔：藏在体内的格子/腔"),
        ("过渡型", "其余（半露半藏）", KIND_COL["过渡型"], "ball", "PK", "关节球 / 球囊：介于两者之间"),
    ]
    y = 128
    for (name, cond, col, key, fam, desc) in rows:
        cv.d.rounded_rectangle([40, y, 1560, y + 104], radius=12,
                               fill=(252, 253, 255), outline=(224, 230, 236))
        cv.d.rounded_rectangle([40, y, 54, y + 104], radius=6, fill=col)
        _morph_icon(cv, 122, y + 52, key, fam, 104)
        cv.txt(228, y + 28, name, 19, True, col, "lm")
        cv.txt(228, y + 56, "条件：" + cond, 11.5, False, INK2, "lm")
        cv.txt(560, y + 30, desc, 12.5, False, INK, "lm")
        cv.txt(560, y + 58, "示例形态：" + MZH.get(key, key) + "（" + "·".join(MTAGS.get(key, [])[:3]) + "）",
               11, False, INK2, "lm")
        y += 112
    cv.txt(40, y + 24, "判定顺序：受力优先（承力型）→ 外缘且带触肢（感受/抓握型）→ 外缘（表面型）→ 内藏（内脏型）→ 其余过渡型。",
           12, False, INK2, "lm")
    cv.save(path)
    print("saved", path)


def page_organs(path="images/t73_organs.png"):
    data = P.load_data()
    by = {m["mid"]: m for m in data["molecules"]}
    picks = [by[p] for p in PICKS if p in by]
    cw, ch = 1540, 480
    cv = S.Canvas(1600, 150 + len(picks) * (ch + 22), (255, 255, 255))
    cv.txt(40, 46, "T73 分化后的整体形体：每个器官的整个形态就是它分化出的形态", 26, True, INK, "lm")
    cv.txt(40, 78, "器官不再套在家族容器里：它的整个外形就是分化形态（六边主控腔、椭圆储腔、环形神经节…），相邻器官互相压叠成一个身体；右侧写明每个器官为什么长成这样。",
           12.5, False, INK2, "lm")
    for i, mol in enumerate(picks):
        y = 118 + i * (ch + 22)
        cv.d.rounded_rectangle([24, y, 1576, y + ch], radius=14, fill=(252, 253, 255),
                               outline=(226, 232, 238))
        info = T73B.draw_organ_body(cv, mol, (36, y + 34, 690, ch - 60), max_s=46,
                                    show_badges=True)
        organs = info.get("organs") or []
        cv.txt(750, y + 26, mol["mid"] + "   " + mol["formula"], 19, True, INK, "lm")
        tr = R2.molecule_traits(mol)
        cv.txt(750, y + 54, tr.get("name") or "", 13, True, (0x2c, 0x3e, 0x50), "lm")
        cv.txt(750, y + 78, "%d 原子 · %d 骨架 · %d 桥 · 器官 %d 个 · 生命类 %s" % (
            mol["n_atoms"], len(mol["skeletons"]), len(mol["bridges"]), len(organs),
            tr.get("kind_zh", "")), 11, False, INK2, "lm")
        yy = y + 108
        cv.txt(750, yy, "器官：长成的形态（整块外形）← 几何依据 → 擅长", 12, True, INK, "lm")
        yy += 22
        for og in organs[:7]:
            reason = og.get("reason", "")
            kind = reason.split("→")[-1] if "→" in reason else "过渡型"
            col = KIND_COL.get(kind, INK)
            cv.d.ellipse([750, yy - 9, 768, yy + 9], outline=col, width=2)
            cv.txt(759, yy, str(og.get("num", "")), 10, True, col, "mm")
            cv.txt(778, yy, MZH.get(og.get("morph"), og.get("morph")), 11.5, True, INK, "lm")
            cv.txt(880, yy, kind, 11, False, col, "lm")
            cv.txt(968, yy, reason.split("→")[0] if "→" in reason else reason, 10.5, False, INK2, "lm")
            tags = MTAGS.get(og.get("morph"), [])
            cv.txt(1150, yy, "·".join(AB.ABIL[t]["zh"] for t in tags[:3] if t in AB.ABIL),
                   10.5, False, (0x1e, 0x84, 0x49), "lm")
            yy += 20
        cv.txt(750, y + ch - 30, "身体突起上的编号 = 右侧器官编号（体表露出的器官才有编号）", 10.5, False, INK2, "lm")
    cv.save(path)
    print("saved", path)


def main():
    page_rules()
    page_organs()


if __name__ == "__main__":
    main()
