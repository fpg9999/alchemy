# -*- coding: utf-8 -*-
"""t4_lattice_csp：用"位置模 6"的 CSP 做可摆放性必要条件检验。

依据：允许的键偏移 S/C/L 都是 [-2,2]^2 内的小向量，模 6 互不相同。
若分子可摆放，则每个原子位置 (q,r) mod 6 的赋值满足：
  对每条边 (i,j)： (res_j - res_i) mod 6  ∈  { o mod 6 : o ∈ allowed_offsets(cat_i, cat_j) }。
这是必要条件（还能再叠加"整格坐标一致性"检查）。若 CSP 无解 → 分子一定摆不出。

另加颜色/奇偶 12 类 CSP 作为更粗的必要条件（快）。
"""
import json
import sys
import time
from collections import deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
MOD = 6
ALL_RES = [(q, r) for q in range(MOD) for r in range(MOD)]


def norm6(x, y):
    return (x % MOD, y % MOD)


def allowed_offsets(a, b):
    return P.allowed(a, b)


def edge_ok(resi, resj, offsets):
    d = norm6(resj[0] - resi[0], resj[1] - resi[1])
    for (dx, dy) in offsets:
        if norm6(dx, dy) == d:
            return True
    return False


def color_parity_ok(a, b):
    """返回允许的 (color_diff_zero, parity_same) 组合集合; 颜色 0..2, 奇偶类 (q%2,r%2)"""
    cats = {P.CAT[a], P.CAT[b]}
    types = set()
    for t, offs in (("S", P.S_SET), ("C", P.C_SET), ("L", P.L_SET)):
        if offs is not None and offs & P.allowed(a, b):
            types.add(t)
    # 仅用于快速检查：见分析
    if cats == {"聚"}:
        return ("S",)
    if cats == {"动"}:
        return ("C",)
    if cats == {"散"}:
        return ("L",)
    if cats == {"聚", "动"}:
        return ("S", "C")
    if cats == {"动", "散"}:
        return ("C", "L")
    return ("S", "L")


class Csp:
    def __init__(self, atoms, edges):
        self.n = len(atoms)
        self.atoms = atoms
        self.adj = [[] for _ in range(self.n)]
        for (i, j, m) in edges:
            self.adj[i].append(j)
            self.adj[j].append(i)
        self.offs = {}
        for i in range(self.n):
            for j in self.adj[i]:
                self.offs[(i, j)] = allowed_offsets(atoms[i], atoms[j])
        self.res = [None] * self.n
        self.sols = []

    def neighbors_ok(self, v, cand):
        for u in self.adj[v]:
            if self.res[u] is not None and not edge_ok(self.res[u], cand, self.offs[(u, v)]):
                return False
        return True

    def solve_one(self, budget=2_000_000):
        self.steps = 0
        order = sorted(range(self.n), key=lambda i: -len(self.adj[i]))
        # BFS-like: choose most constrained
        assigned = [False] * self.n

        def dfs(pos):
            if self.steps > budget:
                raise TimeoutError
            if pos == self.n:
                return True
            # choose unassigned atom with fewest candidate residues
            best_v, best_dom = None, None
            for v in range(self.n):
                if assigned[v]:
                    continue
                dom = [c for c in ALL_RES if self.neighbors_ok(v, c)]
                if best_dom is None or len(dom) < len(best_dom):
                    best_v, best_dom = v, dom
                    if len(dom) == 0:
                        break
            if not best_dom:
                return False
            assigned[best_v] = True
            for c in best_dom:
                self.steps += 1
                self.res[best_v] = c
                if dfs(pos + 1):
                    return True
            self.res[best_v] = None
            assigned[best_v] = False
            return False

        t0 = time.time()
        try:
            ok = dfs(0)
        except TimeoutError:
            ok = False
            print("   [timeout]")
        return ok, time.time() - t0, getattr(self, "steps", 0)


def build_molecule(elems, feed):
    atoms = P.vec_to_atoms(tuple(feed), elems)
    mols = P.simulate(atoms)
    if not mols:
        return None, None
    big = max(mols, key=lambda m: len(m["atoms"]))
    return big["atoms"], big["edges"]


def main():
    cases = [
        ("T97(已验证可摆)", P.ORDER, [3, 8, 15, 10, 1, 0, 36, 22, 2]),
        ("T68(已验证可摆)", P.ORDER, [6, 2, 0, 24, 8, 8, 6, 6, 8]),
        ("OXKA154(未验证)", ["O", "X", "K", "A"], [71, 35, 27, 28]),
        ("T129(未验证)", P.ORDER, [6, 12, 16, 13, 3, 0, 52, 24, 3]),
        ("T160(未验证)", P.ORDER, [10, 20, 16, 15, 0, 1, 66, 30, 2]),
    ]
    out = {}
    for name, elems, feed in cases:
        atoms, edges = build_molecule(elems, feed)
        if atoms is None:
            print(name, "sim fail")
            continue
        csp = Csp(atoms, edges)
        ok, dt, steps = csp.solve_one()
        print(f"{name}: n={len(atoms)} mod6-CSP={ok} ({dt:.1f}s, {steps} steps)", flush=True)
        out[name] = {"n": len(atoms), "csp_sat": ok}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
