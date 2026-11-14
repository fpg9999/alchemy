"""炼金术游戏：十元素 / 三键型 的几何化学模型。

坐标约定
--------
正六边形密铺中，用 axial 坐标 (q, r) 标记每个格子（元素）。三种键恰好对应三组
"相对位置"，每组 6 个方向、共 18 个成键位置：

  短键（聚素之间）：两格共边            offset = 6 个近邻
  长键（散素之间）：两格之间正好隔一个空格 offset = 2 * 6 个近邻（共线、中间格必须为空）
  角键（动素之间）：两格"角对角，中间恰好隔一条格边"
                     offset = 距 2 的 6 个"斜向"格

关键数学事实：三种键各自构成的图，都是同一个三角格子（triangular lattice）T。
  短键：全部格子上是 T（密度 1）
  角键：格子按 index-3 子格分成 3 份，每份内部是 T（密度 1/3）
  长键：格子按 (q,r) 的奇偶分成 4 份，每份内部是 T（密度 1/4）
因此"一个分子 = T 的连通诱导子图，每个格子的度数 = 该元素价数"。
"""

from collections import defaultdict

# ---------------------------------------------------------------- 基本几何
T_NBRS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1))

# 角键偏移（距 2、非共线的那 6 个格子）
CORNER_OFF = ((1, 1), (2, -1), (1, -2), (-1, -1), (-2, 1), (-1, 2))
# 长键偏移（共线、距 2，中间格必须为空）
LONG_OFF = ((2, 0), (0, 2), (-2, 0), (0, -2), (2, -2), (-2, 2))

CATS = {
    "ju":   {"name": "聚素", "bond": "短键", "off": None},
    "dong": {"name": "动素", "bond": "角键", "off": CORNER_OFF},
    "san":  {"name": "散素", "bond": "长键", "off": LONG_OFF},
}

ELEMS = {
    "O": ("秩", "ju", 3), "X": ("晶", "ju", 2), "C": ("冰", "ju", 1),
    "P": ("势", "dong", 3), "W": ("流", "dong", 2), "L": ("电", "dong", 1),
    "K": ("沌", "san", 3), "A": ("气", "san", 2), "F": ("焰", "san", 1),
}
VAL2SYM = {cat: {v: s for s, (_, c, v) in ELEMS.items() if c == cat} for cat in CATS}

# 分子格坐标 (u, v)∈T  ->  六边形格子 axial 坐标 (q, r)
EMBED = {
    "ju":   lambda u, v: (u, v),                       # 短键：原样
    "dong": lambda u, v: (u + 2 * v, u - v),           # 角键：基 (1,1),(2,-1)
    "san":  lambda u, v: (2 * u, 2 * v),               # 长键：整体放大 2 倍
}


def add(p, d):
    return (p[0] + d[0], p[1] + d[1])


def neighbors(p):
    return [add(p, d) for d in T_NBRS]


# ---------------------------------------------------------------- T 上的形状
def degrees(S):
    S = set(S)
    return {p: sum(1 for q in neighbors(p) if q in S) for p in S}


def connected(S):
    S = set(S)
    if not S:
        return False
    start = next(iter(S))
    seen, stack = {start}, [start]
    while stack:
        p = stack.pop()
        for q in neighbors(p):
            if q in S and q not in seen:
                seen.add(q)
                stack.append(q)
    return len(seen) == len(S)


def _rot60(p):
    q, r = p
    return (-r, q + r)


def _reflect(p):
    return (p[1], p[0])


def _transforms():
    ts = []
    for k in range(6):
        def rot(p, k=k):
            x = p
            for _ in range(k):
                x = _rot60(x)
            return x

        def rot_ref(p, k=k):
            x = _reflect(p)
            for _ in range(k):
                x = _rot60(x)
            return x
        ts.append(rot)
        ts.append(rot_ref)
    return ts


TRANSFORMS = _transforms()


def canon(S):
    """平移 + 12 个六边形对称（6 旋转 × 反射）下的规范形。"""
    best = None
    for f in TRANSFORMS:
        img = [f(p) for p in S]
        mq = min(p[0] for p in img)
        mr = min(p[1] for p in img)
        norm = tuple(sorted((p[0] - mq, p[1] - mr) for p in img))
        if best is None or norm < best:
            best = norm
    return best


def signature(S):
    """返回 (n1, n2, n3)：度数=1/2/3 的格子各有多少个。"""
    ds = degrees(S)
    cnt = {1: 0, 2: 0, 3: 0}
    for d in ds.values():
        if d not in cnt:
            return None
        cnt[d] += 1
    return (cnt[1], cnt[2], cnt[3])


def valid_shape(S):
    sig = signature(S)
    return sig is not None and connected(S)


def enumerate_shapes(maxn):
    """所有 <=maxn 格、连通、诱导度数<=3 的形状（规范形）。"""
    out = {1: set(), 2: set()}
    level = {((0, 0),)}
    out[1] = set(level)
    for n in range(2, maxn + 1):
        nxt = set()
        for tup in level:
            S = set(tup)
            for p in S:
                for d in T_NBRS:
                    q = add(p, d)
                    if q in S:
                        continue
                    S2 = S | {q}
                    if sum(1 for x in neighbors(q) if x in S2) > 3:
                        continue
                    ok = True
                    for nb in neighbors(q):
                        if nb in S:
                            if sum(1 for x in neighbors(nb) if x in S2) > 3:
                                ok = False
                                break
                    if ok:
                        nxt.add(canon(S2))
        level = nxt
        out[n] = set(level)
    return out


# ---------------------------------------------------------------- 六边形格子里的直接校验
def hex_bonds(S_hex, cat):
    """直接在格子坐标上找出所有成键对。"""
    S = set(S_hex)
    pairs = []
    for i, p in enumerate(S_hex):
        for q in S_hex[i + 1:]:
            d = (q[0] - p[0], q[1] - p[1])
            off = CATS[cat]["off"]
            if cat == "ju":
                if d in T_NBRS:
                    pairs.append((p, q, "short"))
            elif d in off:
                if cat == "dong":
                    pairs.append((p, q, "corner"))
                else:  # san
                    mid = ((p[0] + q[0]) // 2, (p[1] + q[1]) // 2)
                    if mid not in S:
                        pairs.append((p, q, "long"))
    return pairs


def check_molecule(cells_uv, cat):
    """用两套独立方法校验一个分子。cells_uv 是 T 坐标里的形状。"""
    cells_hex = [EMBED[cat](u, v) for (u, v) in cells_uv]
    assert len(set(cells_hex)) == len(cells_hex), "格子重复"

    ds = degrees(cells_uv)
    bonds = hex_bonds(cells_hex, cat)
    deg_hex = defaultdict(int)
    for p, q, _ in bonds:
        deg_hex[p] += 1
        deg_hex[q] += 1

    problems = []
    for (u, v) in cells_uv:
        h = EMBED[cat](u, v)
        if deg_hex.get(h, 0) != ds[(u, v)]:
            problems.append(f"格子 {h}: T度={ds[(u,v)]} 但格子度={deg_hex.get(h,0)}")
    expected_edges = sum(ds.values()) // 2
    if len(bonds) != expected_edges:
        problems.append(f"边数不符: 格子={len(bonds)}, 期望={expected_edges}")
    if not connected(cells_uv):
        problems.append("不连通")
    n_atoms = len(cells_uv)
    if 2 * expected_edges != sum(ds.values()):
        problems.append("度数之和为奇数")
    # 每个格子度数必须等于某个元素的价数
    for d in ds.values():
        if d not in (1, 2, 3):
            problems.append(f"度 {d} 不是 1/2/3")
    return {
        "cat": cat,
        "cells_hex": cells_hex,
        "degrees": ds,
        "bonds": bonds,
        "n_atoms": n_atoms,
        "n_bonds": len(bonds),
        "signature": signature(cells_uv),
        "problems": problems,
    }


def formula(cells_uv, cat):
    sig = signature(cells_uv)
    v2s = VAL2SYM[cat]
    parts = []
    for deg, cnt in ((3, sig[2]), (2, sig[1]), (1, sig[0])):
        if cnt:
            parts.append(f"{v2s[deg]}{cnt if cnt > 1 else ''}")
    return "".join(parts)


SUBS = {str(i): c for i, c in enumerate("₀₁₂₃₄₅₆₇₈₉")}


def pretty(formula_str):
    return "".join(SUBS.get(ch, ch) for ch in formula_str)
