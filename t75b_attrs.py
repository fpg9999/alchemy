# -*- coding: utf-8 -*-
"""T75b 逐骨架属性：每个骨架自己算 硬度/粘性/温度。

用户 m02416：
- 属性按**每个骨架**算，不按整个物质；
- 骨架用它"拥有的元素"和"连接到的元素"来算；
- **用于连接两个骨架的二价桥**（role == "bridge"）不计入任何属性，只有连接功能；
- 骨架内桥 / 支臂 / 端帽 等挂在骨架上的元素计入该骨架。
"""
from collections import Counter

HARD_W = {"O": 1.20, "P": 0.90, "K": 0.60}
STICK_W = {"X": 1.00, "W": 1.40, "A": 0.40}
TEMP_W = {"C": -2.00, "L": 0.50, "F": 3.00}
ELEM_ZH = {"O": "秩", "P": "势", "K": "沌", "X": "晶", "W": "流", "A": "气", "C": "冰", "L": "电", "F": "焰"}


def _parts(cnt, table):
    return [("%s%s" % (ELEM_ZH[e], e), cnt.get(e, 0), w) for e, w in table.items() if cnt.get(e, 0)]


def _val(cnt, table):
    return round(sum(cnt.get(e, 0) * w for e, w in table.items()), 2)


def skeleton_attrs(mol):
    """返回每个骨架的属性：硬度（三价）、粘性（挂在这块上的二价）、温度（挂在这块上的一价）。

    桥（role=="bridge"）不参与计算；骨架内桥、支臂、端帽等都归到所连的骨架。
    """
    atoms = mol["atoms"]
    role = mol.get("role") or {}
    adj = {}
    for (a, b, m) in mol["edges"]:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    atom2sk = {}
    for i, sk in enumerate(mol["skeletons"]):
        for a in sk["idx"]:
            atom2sk[a] = i
    out = []
    for i, sk in enumerate(mol["skeletons"]):
        tri = Counter(atoms[a] for a in sk["idx"])
        hard = _val(tri, HARD_W)
        div = Counter()
        mono = Counter()
        for a in range(len(atoms)):
            if a in atom2sk:
                continue
            r = role.get(str(a), role.get(a))
            if r == "bridge":
                continue
            # 判断它属于哪个骨架：沿邻接找最近的骨架原子
            tgt = None
            for nb in adj.get(a, []):
                if nb in atom2sk:
                    tgt = atom2sk[nb]
                    break
            if tgt is None:
                # 二步（支臂链：atom - div - skel）
                for nb in adj.get(a, []):
                    for nb2 in adj.get(nb, []):
                        if nb2 in atom2sk:
                            tgt = atom2sk[nb2]
                            break
                    if tgt is not None:
                        break
            if tgt is None or tgt != i:
                continue
            el = atoms[a]
            if el in STICK_W:
                div[el] += 1
            elif el in TEMP_W:
                mono[el] += 1
        visc = _val(div, STICK_W)
        temp = _val(mono, TEMP_W)
        out.append({
            "sk": sk, "i": i, "num": sk.get("num", i + 1),
            "formula": sk.get("formula"),
            "hardness": hard, "viscosity": visc, "temperature": temp,
            "hard_parts": _parts(tri, HARD_W),
            "visc_parts": _parts(div, STICK_W),
            "temp_parts": _parts(mono, TEMP_W),
            "n_bridge_excluded": sum(1 for a in range(len(atoms))
                                     if role.get(str(a), role.get(a)) == "bridge"
                                     and any(nb in atom2sk and atom2sk[nb] == i for nb in adj.get(a, []))),
        })
    return out


def ranges(molecules):
    hs, vs, ts = [], [], []
    for m in molecules:
        for a in skeleton_attrs(m):
            hs.append(a["hardness"])
            vs.append(a["viscosity"])
            ts.append(a["temperature"])
    return (0.0, max(hs) or 1.0), (0.0, max(vs) or 1.0), (min(ts or [0]), max(ts or [1]))
