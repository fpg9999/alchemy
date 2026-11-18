# -*- coding: utf-8 -*-
"""T73d 大分子有机生命：按能力与结构判定（生命度 ≥5）。"""
import json
from collections import Counter

import t68_shapes as S
import t69_pieces as P
import pot_all as PA
import t72_morphs as M
import t73_body as T73B
import t74_rules as R
import t72_abilities as AB
from t73_inorganic import norm, candidates

INK = (40, 52, 66)
INK2 = (100, 116, 132)
MZH = {}
for _fam, _lst in M.MORPHS.items():
    for _e in _lst:
        MZH[_e[0]] = _e[1]

LIFE_ZH = {"differentiate": "分化", "move": "移动", "sense": "感知", "store": "储能",
           "grasp": "抓取", "adhere": "粘附", "symbiosis": "共生", "pump": "泵送",
           "repair": "自修", "signal": "信号", "defend": "防御", "conduct": "导电",
           "support": "结构支撑", "heat": "耐热", "rigid": "刚性骨架", "insulate": "绝缘",
           "sensor": "感知", "flex": "柔韧", "compress": "抗压", "tensile": "抗拉",
           "tough": "韧性", "porous": "多孔", "dense": "致密", "laminate": "层状",
           "crystallize": "结晶", "cleavage": "分解", "catalyze": "催化", "synthesis": "合成",
           "encode": "信号编码", "memory": "状态记忆", "bud": "出芽", "metamorph": "变态",
           "presso": "压力感", "photo": "光感", "chemo": "化学感", "swarm": "群体协调"}


def zh_of(key):
    a = AB.ABIL.get(key)
    return a["zh"] if a else LIFE_ZH.get(key, key)


def page(path="images/t73_organic.png"):
    rows = []
    seen = set()
    for mol, src in candidates():
        key = mol.get("mol_label") or mol["formula"]
        if key in seen:
            continue
        seen.add(key)
        try:
            c = R.classify(mol)
        except Exception:
            continue
        if c["kind"] == "有机物" and mol["n_atoms"] >= 19:
            rows.append((c, mol))
    rows.sort(key=lambda r: (-r[0]["score"], -r[1]["n_atoms"]))
    picks = rows[:14]

    cw, ch = 780, 392
    cols = 2
    nrows = (len(picks) + cols - 1) // cols
    cv = S.Canvas(40 + cols * cw, 190 + nrows * ch, (255, 255, 255))
    cv.txt(40, 46, "T73 大分子有机生命：能力与结构长出来的“生物”", 26, True, INK, "lm")
    cv.txt(40, 78, "有机 / 无机按结构门控生命度判定：≥5 有机物（8 以上 = 有机生命，5~8 = 拟生命）；"
                   "状态按 X>W>A，硬度按 O>P>K，高温/低温/导电按 C>L>F。", 12.3, False, INK2, "lm")
    n_life = sum(1 for r in rows if r[0]["score"] >= 8)
    cv.txt(40, 102, "共 %d 个大分子有机物（其中有机生命 %d、拟生命 %d），这里展示生命度最高的 14 个。" % (
        len(rows), n_life, len(rows) - n_life), 11.5, False, INK2, "lm")
    cv.txt(40, 124, "身体上的每个器官都是它整块长成的分化形态；卡片右侧是能力与器官分工。", 11.5, False, INK2, "lm")

    for i, (c, mol) in enumerate(picks):
        cc, r = i % cols, i // cols
        x = 40 + cc * cw
        y = 150 + r * ch
        cv.d.rounded_rectangle([x, y, x + cw - 18, y + ch - 18], radius=12,
                               fill=(252, 253, 255), outline=(226, 232, 238))
        info = T73B.draw_organ_body(cv, mol, (x + 12, y + 22, 330, ch - 80), max_s=40)
        organs = info.get("organs") or []
        tr = c["traits"]
        tx = x + 356
        cnt = Counter(mol["atoms"])
        col = (0x1e, 0x84, 0x49) if c["score"] >= 8 else (0x16, 0xa0, 0x85)
        cv.txt(tx, y + 22, mol["formula"], 15, True, INK, "lm")
        cv.txt(tx + 300, y + 22, ("有机生命" if c["score"] >= 8 else "拟生命"), 11.5, True, col, "lm")
        cv.txt(tx, y + 46, "生命分 %.1f · %s · %s · %s" % (
            c["score"], c["state"], c["hardness"], c["thermal"]), 11, False, INK, "lm")
        nm = tr.get("name") or ""
        if nm:
            cv.txt(tx, y + 68, nm[:34], 10.5, False, (0x2c, 0x3e, 0x50), "lm")
        cv.txt(tx, y + 90, "%d 原子 · %d 骨架 · %d 桥 · 端帽 %d · 支臂 %d" % (
            mol["n_atoms"], len(mol["skeletons"]), len(mol["bridges"]),
            len(mol["decoration"].get("mono", [])), len(mol["decoration"].get("arms", []))),
               9.5, False, INK2, "lm")
        # 器官形态
        cv.txt(tx, y + 116, "器官（整块外形 = 分化形态）", 10.5, True, INK, "lm")
        yy = y + 136
        seen_zh = []
        for og in organs:
            zh = MZH.get(og.get("morph"), og.get("morph"))
            reason = og.get("reason", "")
            kind = reason.split("→")[-1] if "→" in reason else "—"
            if zh in seen_zh:
                continue
            seen_zh.append(zh)
            cv.txt(tx, yy, "· %s（%s）" % (zh, kind), 10, False, INK, "lm")
            yy += 16
            if yy > y + ch - 96:
                break
        # 能力
        ab = tr.get("abilities") or {}
        top = sorted(ab.items(), key=lambda kv: -kv[1])[:6]
        names = [zh_of(k) + "%s" % ("Ⅲ" if v >= 3 else ("Ⅱ" if v >= 2 else "Ⅰ"))
                 for k, v in top if zh_of(k) != k] or [zh_of(k) for k, v in top]
        cv.txt(tx, y + ch - 74, "能力：" + " · ".join(names), 10, False, INK, "lm")
        place = mol["place"]
        pl = [tuple(place[str(j)]) for j in range(len(place))] if isinstance(place, dict) else [tuple(p) for p in place]
        bt = Counter()
        for (a, b, mm) in mol["edges"]:
            bt[PA.classify_offset((pl[b][0] - pl[a][0], pl[b][1] - pl[a][1])) or "?"] += 1
        cv.txt(tx, y + ch - 54, "键：" + " · ".join("%s×%d" % ({"S": "S 短", "C": "C 角", "L": "L 长"}.get(k, k), v)
                                                   for k, v in bt.items()), 9.5, False, INK2, "lm")
        flags = list(tr.get("life_flags", {}).keys())
        cv.txt(tx, y + ch - 36, "生命特征：" + "、".join(LIFE_ZH.get(f, f) for f in flags), 9.5, False, INK2, "lm")
    cv.save(path)
    print("saved", path, "organic", len(rows), "life", n_life)


def main():
    page()


if __name__ == "__main__":
    main()
