# -*- coding: utf-8 -*-
"""跨大类键规则校验（v2）

同一根键允许的键型 = 两端大类各自键型的并集：
  聚 -> S, 动 -> C, 散 -> L
  所以 聚-聚:S; 动-动:C; 散-散:L; 聚-动:S|C; 动-散:C|L; 聚-散:S|L（最后一条待用户确认）
相邻但未写键不算成键（用户已确认）。
"""
import math

S_OFF = {1: (0, 2), 3: (1, 1), 5: (1, -1), 7: (0, -2), 9: (-1, -1), 11: (-1, 1)}
C_OFF = {2: (1, 3), 4: (2, 0), 6: (1, -3), 8: (-1, -3), 10: (-2, 0), 12: (-1, 3)}
L_OFF = {k: (2 * x, 2 * y) for k, (x, y) in S_OFF.items()}
OFFS = {"S": S_OFF, "C": C_OFF, "L": L_OFF}
VAL = {"O": 3, "X": 2, "C": 1, "P": 3, "W": 2, "L": 1, "K": 3, "A": 2, "F": 1}
CAT = {"O": "聚", "X": "聚", "C": "聚", "P": "动", "W": "动", "L": "动", "K": "散", "A": "散", "F": "散"}
TYPEOF = {"聚": "S", "动": "C", "散": "L"}
CN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电", "K": "沌", "A": "气", "F": "焰"}


def allowed(t, ca, cb):
    """键型 t 能否用于大类 ca 与 cb 之间。"""
    types = {TYPEOF[ca], TYPEOF[cb]}
    return t in types


def parse(entry):
    elem, x, y = entry[0], entry[1], entry[2]
    flat = []
    for b in entry[3:]:
        if isinstance(b, (list, tuple)):
            flat.extend(b)
        else:
            flat.append(b)
    bonds = [(b[0], int(b[1:])) for b in flat]
    return elem, x, y, bonds


def check_mol(name, entries, verbose=True):
    errs, warns = [], []
    cells = {}
    for e in entries:
        elem, x, y, bonds = parse(e)
        if (x, y) in cells:
            errs.append(f"坐标重复 {(x, y)}")
        if (x - y) % 2 != 0:
            errs.append(f"({x},{y}) 不是合法格子（X、Y 必须同奇偶）")
        if len(bonds) != VAL[elem]:
            errs.append(f"{elem}({x},{y}) 有 {len(bonds)} 根键，但价数={VAL[elem]}")
        for (t, k) in bonds:
            if k not in OFFS[t]:
                errs.append(f"{t}{k} 方向编号不适用于 {t} 键")
        cells[(x, y)] = (elem, bonds)

    for (x, y), (elem, bonds) in cells.items():
        ca = CAT[elem]
        for (t, k) in bonds:
            dx, dy = OFFS[t][k]
            q = (x + dx, y + dy)
            if q not in cells:
                errs.append(f"({x},{y}) 的 {t}{k} 指向空位 {q}")
                continue
            partner, pbonds = cells[q]
            cb = CAT[partner]
            if not allowed(t, ca, cb):
                errs.append(f"{elem}({ca})-{partner}({cb}) 之间不能用 {t} 键")
            rk = k + 6 if k <= 6 else k - 6
            if (t, rk) not in pbonds:
                errs.append(f"({x},{y}) 的 {t}{k} 指向 {q}，但对端没有 {t}{rk}")
            if t == "L":
                mid = (x + dx // 2, y + dy // 2)
                if mid in cells:
                    errs.append(f"长键 {t}{k} 的中间格 {mid} 有元素（必须为空）")

    for (x, y), (elem, bonds) in cells.items():
        for (t, k) in bonds:
            dx, dy = OFFS[t][k]
            q = (x + dx, y + dy)
            if q in cells:
                rk = k + 6 if k <= 6 else k - 6
                if cells[q][1].count((t, rk)) < bonds.count((t, k)):
                    warns.append(f"键数不对称：({x},{y}) {t}{k} 与 {q}")

    xs = [p[0] for p in cells]
    ys = [p[1] for p in cells]
    if min(xs) != 0 or min(ys) != 0:
        errs.append(f"最左下角不是 (0,0)：minX={min(xs)}, minY={min(ys)}")
    if verbose:
        print(f"\n=== {name} ===")
        for e in entries:
            print("   ", e)
        print("   错误:", errs if errs else "无")
        print("   提示:", warns if warns else "无")
    return errs, warns, cells


EXAMPLES = [
    # ---- 跨类：聚-动 ----
    ("秩电₃（聚-动，用 C 键）", [("L", 0, 0, ["C2"]), ("L", 0, 6, ["C6"]),
                           ("O", 1, 3, ["C4", "C8", "C12"]), ("L", 3, 3, ["C10"])]),
    ("势冰₃（聚-动，用 S 键）", [("C", 0, 0, ["S3"]), ("C", 1, 3, ["S7"]),
                           ("C", 2, 0, ["S11"]), ("P", 1, 1, ["S1", "S5", "S9"])]),
    ("冰₂流（聚-动，用 S 键）", [("W", 0, 0, ["S1", "S3"]), ("C", 0, 2, ["S7"]),
                           ("C", 1, 1, ["S9"])]),
    # ---- 跨类：同一分子里 S 和 C 都用上 ----
    ("秩冰₂电（聚-聚 S + 聚-动 C）", [("C", 0, 0, ["S3"]), ("C", 1, 3, ["S7"]),
                              ("O", 1, 1, ["S1", "S9", "C4"]), ("L", 3, 1, ["C10"])]),
    # ---- 跨类：动-散 ----
    ("流焰₂（动-散，用 L 键）", [("W", 0, 0, ["L1", "L3"]), ("F", 0, 4, ["L7"]),
                          ("F", 2, 2, ["L9"])]),
    ("沌电₃（动-散，用 C 键）", [("L", 0, 0, ["C2"]), ("L", 0, 6, ["C6"]),
                          ("K", 1, 3, ["C4", "C8", "C12"]), ("L", 3, 3, ["C10"])]),
    # ---- 跨类：聚-散（规则待确认） ----
    ("秩焰₃（聚-散，用 L 键，待确认）", [("F", 0, 0, ["L3"]), ("F", 2, 6, ["L7"]),
                                ("F", 4, 0, ["L11"]), ("O", 2, 2, ["L1", "L5", "L9"])]),
]

if __name__ == "__main__":
    ok = 0
    for name, entries in EXAMPLES:
        errs, warns, cells = check_mol(name, entries)
        if not errs:
            ok += 1
    print(f"\n通过：{ok}/{len(EXAMPLES)}")
