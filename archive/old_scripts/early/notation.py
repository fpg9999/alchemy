# -*- coding: utf-8 -*-
"""按用户新规则（同对元素之间可连 1~3 根键）的记号校验器。

记号： （元素，X，Y，键1，键2，...）
方向：正上方 = 1，顺时针每 30° +1，共 12 个方向。
  S 短键（聚素）：奇数方向 1,3,5,7,9,11
  C 角键（动素）：偶数方向 2,4,6,8,10,12
  L 长键（散素）：奇数方向 1,3,5,7,9,11（与短键同轴，距离是两倍，中间格必须为空）
坐标：X+2 是向右一格，Y+2 是向上一格，(X+1,Y+1) 是右上斜一格。
格子只出现在 X、Y 同奇偶的位置。
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


def parse(entry):
    """（O,0,0,S1,S1,S3） -> (elem, x, y, [(type,dir),...])"""
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
            errs.append(f"坐标重复 {(x,y)}")
        if (x - y) % 2 != 0:
            errs.append(f"({x},{y}) 不是合法格子（X、Y 必须同奇偶）")
        if len(bonds) != VAL[elem]:
            errs.append(f"{elem}({x},{y}) 有 {len(bonds)} 根键，但价数={VAL[elem]}")
        typ = TYPEOF[CAT[elem]]
        for (t, k) in bonds:
            if t != typ:
                errs.append(f"{elem} 是{CAT[elem]}素，只能用 {typ} 键，却写了 {t}")
            if k not in OFFS[t]:
                errs.append(f"{t}{k} 方向编号不适用于 {t} 键")
        cells[(x, y)] = (elem, bonds)

    # 逐根键检查"对端存在且互相承认"
    for (x, y), (elem, bonds) in cells.items():
        for (t, k) in bonds:
            dx, dy = OFFS[t][k]
            q = (x + dx, y + dy)
            if q not in cells:
                errs.append(f"({x},{y}) 的 {t}{k} 指向空位 {q}")
                continue
            partner, pbonds = cells[q]
            rev = 6 if k <= 6 else -6
            rk = k + rev
            if (t, rk) not in pbonds:
                errs.append(f"({x},{y}) 的 {t}{k} 指向 {q}，但对端没有 {t}{rk}")
            if t == "L":
                mid = (x + dx // 2, y + dy // 2)
                if mid in cells:
                    errs.append(f"长键 {t}{k} 的中间格 {mid} 有元素（必须为空）")

    # 数量统计
    for (x, y), (elem, bonds) in cells.items():
        for (t, k) in bonds:
            dx, dy = OFFS[t][k]
            q = (x + dx, y + dy)
            if q in cells:
                partner, pbonds = cells[q]
                rk = k + 6 if k <= 6 else k - 6
                if pbonds.count((t, rk)) < bonds.count((t, k)):
                    warns.append(f"键数不对称：({x},{y}) {t}{k} 写了 {bonds.count((t,k))} 根，对端只写了 {pbonds.count((t,rk))} 根")

    # "多余的相邻但没连键"（提示，不算错）
    for (x, y), (elem, bonds) in cells.items():
        typ = TYPEOF[CAT[elem]]
        for k, (dx, dy) in OFFS[typ].items():
            q = (x + dx, y + dy)
            if q in cells and (typ, k) not in bonds:
                warns.append(f"({x},{y}) 与 {q} 是{typ}键可连位置，但没连键（如果相邻就必须连，这条算错）")

    # 原点 = 最左下角（要求 (0,0) 是 X 最小、Y 最小的元素）
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
    ("秩₂（三重键）", [("O", 0, 0, ["S1", "S1", "S1"]), ("O", 0, 2, ["S7", "S7", "S7"])]),
    ("秩₂晶", [("O", 0, 0, ["S1", "S1", "S3"]), ("O", 0, 2, ["S7", "S7", "S5"]),
              ("X", 1, 1, ["S9", "S11"])]),
    ("冰₂晶", [("C", 0, 0, ["S3"]), ("X", 1, 1, ["S5", "S9"]), ("C", 2, 0, ["S11"])]),
    ("秩冰₃", [("C", 0, 0, ["S3"]), ("O", 1, 1, ["S1", "S5", "S9"]),
              ("C", 1, 3, ["S7"]), ("C", 2, 0, ["S11"])]),
    ("晶₃", [("X", 0, 0, ["S1", "S3"]), ("X", 0, 2, ["S5", "S7"]),
             ("X", 1, 1, ["S9", "S11"])]),
    ("冰₂晶₂", [("C", 0, 0, ["S3"]), ("X", 1, 1, ["S1", "S9"]),
               ("X", 1, 3, ["S3", "S7"]), ("C", 2, 4, ["S9"])]),
    ("电₂", [("L", 0, 0, ["C2"]), ("L", 1, 3, ["C8"])]),
    ("流₃（三角）", [("W", 0, 0, ["C2", "C4"]), ("W", 2, 0, ["C10", "C12"]),
                  ("W", 1, 3, ["C6", "C8"])]),
    ("势电₃", [("L", 0, 0, ["C2"]), ("L", 0, 6, ["C6"]), ("P", 1, 3, ["C4", "C8", "C12"]),
              ("L", 3, 3, ["C10"])]),
    ("焰₂", [("F", 0, 0, ["L1"]), ("F", 0, 4, ["L7"])]),
    ("气₃（三角）", [("A", 0, 0, ["L1", "L3"]), ("A", 0, 4, ["L5", "L7"]),
                  ("A", 2, 2, ["L9", "L11"])]),
    ("沌气₂焰", [("F", 0, 0, ["L3"]), ("K", 2, 2, ["L1", "L3", "L9"]),
                ("A", 2, 6, ["L5", "L7"]), ("A", 4, 4, ["L9", "L11"])]),
    ("沌焰₃", [("F", 0, 0, ["L3"]), ("K", 2, 2, ["L1", "L5", "L9"]),
              ("F", 4, 0, ["L11"]), ("F", 2, 6, ["L7"])]),
]

if __name__ == "__main__":
    ok = 0
    for name, entries in EXAMPLES:
        errs, warns, cells = check_mol(name, entries)
        if not errs:
            ok += 1
    print(f"\n通过：{ok}/{len(EXAMPLES)}")
