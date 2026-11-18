# -*- coding: utf-8 -*-
"""分子同构的规范形（canonical form）。

用途：比较两个分子"是不是同一个结构"（同分异构、骨架库成员判定、去重）。

项目历史上踩过一个坑：早先用的 ``wl_key``（Weisfeiler-Lehman 指纹）**不是同构不变量**——
对称等价原子没有规范破序，同一形态换个输入顺序会得到不同 key，导致：
- 38 形态库中 8/38 形态受影响；
- T38 报出的 97 个"库外块" / 14 个"库外物质"全是假阳性；
- T15 的 695 条虚增（真实 671）。

因此本模块只用 ``mol_label``（带元素标签的多重图规范形，含对称性破序），
它是真正的同构不变量：同图必同 label，不同图必不同 label。
"""
from __future__ import annotations

from collections import defaultdict

from .elements import CAT, ORDER

__all__ = ["mol_label", "canon_signature", "molecule_key", "same_structure"]


def _refine(mat, colors, n):
    """颜色细化（1-WL）：反复用「自身颜色 + 邻居(键级,颜色)多重集」重编号，直到稳定。"""
    while True:
        sigs = []
        for i in range(n):
            sigs.append(
                (colors[i], tuple(sorted((mat[i][j], colors[j]) for j in range(n) if j != i)))
            )
        uniq = sorted(set(sigs))
        idx = {s: k for k, s in enumerate(uniq)}
        new = [idx[s] for s in sigs]
        if new == colors:
            return colors
        colors = new


def _canon_rec(mat, colors, n, best, budget=None):
    """在所有颜色等价类上做分支定界，取字典序最小的证书。"""
    if budget is not None:
        budget[0] -= 1
        if budget[0] < 0:
            raise TimeoutError("canon")
    colors = _refine(mat, colors, n)
    classes = defaultdict(list)
    for i in range(n):
        classes[colors[i]].append(i)
    cell = None
    for key in sorted(classes):
        if len(classes[key]) > 1:
            cell = classes[key]
            break
    if cell is None:
        order = sorted(range(n), key=lambda i: colors[i])
        cert = tuple(order) + tuple(
            mat[order[a]][order[b]] for a in range(n) for b in range(a + 1, n)
        )
        if best[0] is None or cert < best[0]:
            best[0] = cert
        return
    for v in cell:
        cols2 = list(colors)
        cols2[v] = max(colors) + 1
        _canon_rec(mat, cols2, n, best, budget)


def _adjacency(n, edges):
    mat = [[0] * n for _ in range(n)]
    for i, j, m in edges:
        mat[i][j] = mat[j][i] = m
    return mat


def mol_label(atoms, edges) -> str:
    """带元素标签的多重图规范形字符串（同构不变量）。

    返回形如 ``"OXC|102000"``：前半是规范原子序对应的元素串，后半是上三角键级串。
    两个分子同构 <=> ``mol_label`` 完全相等。
    """
    atoms = list(atoms)
    edges = [tuple(e) for e in edges]
    n = len(atoms)
    mat = _adjacency(n, edges)
    base = [ORDER.index(e) for e in atoms]
    best = [None]
    _canon_rec(mat, base, n, best)
    cert = best[0]
    order = list(cert[:n])
    n_edges = n * (n - 1) // 2
    return "".join(atoms[i] for i in order) + "|" + "".join(str(c) for c in cert[n:n + n_edges])


def canon_signature(atoms, edges):
    """按**大类**着色的规范形（只区分聚/动/散，不区分具体元素）。

    用于"几何可摆放性"的缓存 key：摆放只依赖大类，因此可以跨元素复用结果。
    对称度爆炸时退化为带原始标号的 sound 表示（同图必同签名，绝不同图碰撞）。
    """
    atoms = list(atoms)
    edges = [tuple(e) for e in edges]
    n = len(atoms)
    mat = _adjacency(n, edges)
    base = [{"聚": 0, "动": 1, "散": 2}[CAT[e]] for e in atoms]
    best = [None]
    try:
        _canon_rec(mat, base, n, best, [40000])
        return best[0]
    except TimeoutError:
        return ("raw", tuple(base), tuple((i, j, m) for (i, j, m) in edges))


def molecule_key(atoms, edges):
    """``canon_signature`` 的 tuple 版本，可直接当 dict/set key。"""
    sig = canon_signature(atoms, edges)
    n = len(atoms)
    order = list(sig[:n])
    n_edges = n * (n - 1) // 2
    return (n, tuple(order), tuple(sig[n:n + n_edges]))


def same_structure(a1, e1, a2, e2) -> bool:
    """两个分子是否同构（元素级比较）。"""
    return mol_label(a1, e1) == mol_label(a2, e2)
