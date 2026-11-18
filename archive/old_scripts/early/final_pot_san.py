# -*- coding: utf-8 -*-
"""final_pot_san：散素（K/A/F，长键 L）29 种物质导出。

依据 HANDOFF 第 7 节同构：聚素 29 种把 O→K, X→A, C→F 即可；
但必须用散素的 L 几何重新摆放并逐根校验（L 键：同轴 2 格、中间格必须为空，方向为奇数号）。
"""
import json
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
ELEMS = ["K", "A", "F"]


def map_formula_ju2san(vec):
    k, a, f = vec
    return "".join(e + (str(c) if c > 1 else "") for e, c in [("K", k), ("A", a), ("F", f)] if c)


def dir_of_L(d):
    for k, off in P.L_DIRS.items():
        if off == d:
            return k
    raise ValueError(("不是长键偏置", d))


def main():
    ju = json.load(open(BASE + r"\substances.json", encoding="utf-8"))
    out = []
    for x in ju:
        # substances.json 里 vec 顺序是 (O,X,C)；feed 也是 (O,X,C)
        feed = tuple(x["feed"])
        atoms = P.vec_to_atoms(feed, ELEMS)
        mols = P.simulate(atoms)
        assert mols is not None, ("反应失败", x["formula"])
        target = None
        want = map_formula_ju2san(feed)
        # 注意：产物里找与"物质本身"同式的分子（不是投料式；这里 vec=物质成分）
        want = map_formula_ju2san(tuple(x["vec"]))
        for m in mols:
            if P.formula_of(m["atoms"]) == want:
                target = m
                break
        assert target is not None, ("产物里没有", x["formula"], [P.formula_of(m["atoms"]) for m in mols])
        place = P.embed_mol(target["atoms"], target["edges"])
        assert place is not None, ("摆不出来", x["formula"])
        # 校验 L 键中间格为空 + 方向奇数
        occ = set(place.values())
        dirs = []
        for (i, j, mm) in target["edges"]:
            d = (place[j][0] - place[i][0], place[j][1] - place[i][1])
            assert d in P.L_SET, ("不是 L 偏置", want, d)
            mid = P.midpoint_of(d)
            assert (place[i][0] + mid[0], place[i][1] + mid[1]) not in occ, ("L 中间格被占", want)
            dirs.append(dir_of_L(d))
        assert all(k % 2 == 1 for k in dirs)
        out.append({
            "scope": 2,
            "formula": want,
            "vec": [sum(1 for e in target["atoms"] if e == c) for c in ELEMS],
            "feed": list(feed),
            "atoms": target["atoms"],
            "edges": [list(e) for e in target["edges"]],
            "dirs": dirs,
            "bond": "L",
            "place": {str(k): list(v) for k, v in place.items()},
            "place_xy": {str(k): [q, q + 2 * r] for k, (q, r) in place.items()},
            "zh": P.zh_of(target["atoms"]),
            "natoms": len(target["atoms"]),
        })
    out.sort(key=lambda it: (it["natoms"], it["vec"]))
    with open(BASE + r"\substances_san.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("导出", len(out), "种 -> substances_san.json")
    for it in out:
        print(f"  {it['formula']:8s} {it['zh']:8s} {it['natoms']}原子 投料={tuple(it['feed'])} 方向={it['dirs']}")


if __name__ == "__main__":
    main()
