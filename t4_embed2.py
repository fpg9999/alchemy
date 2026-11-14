# -*- coding: utf-8 -*-
"""t4_embed2：可摆放性搜索 v2（前向检查 + MRV + L 中间格多重集 + 节点预算）。

修复：L 中间格用计数（Counter），回溯时只减计数，不会误删其它 L 键共享的中间格。
"""
import sys
import time
from collections import Counter

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P


class Embedder:
    def __init__(self, atoms, edges):
        self.n = len(atoms)
        self.atoms = atoms
        self.adj = [dict() for _ in range(self.n)]
        for (i, j, m) in edges:
            a, b = atoms[i], atoms[j]
            s = P.allowed(a, b)
            self.adj[i][j] = s
            self.adj[j][i] = s
        self.pos = {}
        self.occ = set()
        self.forbidden = Counter()
        self.cand = {}
        self.nodes = 0

    def init_cand(self, v):
        placed = [u for u in self.adj[v] if u in self.pos]
        if not placed:
            return None
        base = None
        for u in placed:
            pu = self.pos[u]
            s = {(pu[0] + dx, pu[1] + dy) for (dx, dy) in self.adj[v][u]}
            base = s if base is None else (base & s)
            if not base:
                return set()
        return {p for p in base if p not in self.occ and self.forbidden[p] == 0}

    def check_midpoints(self, v, p):
        """返回新增禁止格列表；若冲突返回 None。"""
        new_forb = []
        for u in self.adj[v]:
            if u not in self.pos:
                continue
            pu = self.pos[u]
            d = (p[0] - pu[0], p[1] - pu[1])
            if P.classify_offset(d) == "L":
                mid = (pu[0] + d[0] // 2, pu[1] + d[1] // 2)
                if mid in self.occ:
                    return None
                new_forb.append(mid)
        return new_forb

    def refresh(self):
        for v in range(self.n):
            if v not in self.pos:
                c = self.init_cand(v)
                if c is not None:
                    self.cand[v] = c
                else:
                    self.cand.pop(v, None)

    def dfs(self, budget):
        self.nodes += 1
        if self.nodes > budget:
            raise TimeoutError
        if len(self.pos) == self.n:
            return True
        best_v, best_c = None, None
        for v in range(self.n):
            if v in self.pos:
                continue
            c = self.cand.get(v)
            if c is None:
                c = self.init_cand(v)
                if c is None:
                    continue
            if best_c is None or len(c) < len(best_c):
                best_v, best_c = v, c
                if not c:
                    break
        if not best_c:
            return False
        cands = sorted(best_c, key=lambda p: (abs(p[0]) + abs(p[1]), p))
        for p in cands:
            forb = self.check_midpoints(best_v, p)
            if forb is None:
                continue
            self.pos[best_v] = p
            self.occ.add(p)
            for m in forb:
                self.forbidden[m] += 1
            saved = {}
            ok = True
            nbrset = {w for w in self.adj[best_v] if w not in self.pos}
            for w in range(self.n):
                if w in self.pos or w == best_v:
                    continue
                old = self.cand.get(w)
                if old is None:
                    continue
                if w in nbrset:
                    new = self.init_cand(w)
                    if new is None:
                        new = set()
                else:
                    if p in old or any(self.forbidden[f] > 0 for f in forb if f in old):
                        new = {q for q in old if q != p and self.forbidden[q] == 0}
                    else:
                        continue
                if new != old:
                    saved[w] = old
                    self.cand[w] = new
                    if not new:
                        ok = False
                        break
            if ok:
                try:
                    if self.dfs(budget):
                        return True
                finally:
                    pass
            for w, old in saved.items():
                self.cand[w] = old
            for m in forb:
                self.forbidden[m] -= 1
                if self.forbidden[m] == 0:
                    del self.forbidden[m]
            self.occ.discard(p)
            del self.pos[best_v]
        return False


def embed2(atoms, edges, budget=2_000_000):
    emb = Embedder(atoms, edges)
    root = max(range(len(atoms)), key=lambda i: len(emb.adj[i]))
    nbrs = sorted(emb.adj[root].items())
    if not nbrs:
        return {"ok": len(atoms) == 1, "nodes": 1, "seconds": 0}
    nb, offs = nbrs[0]
    # 第一条边按 60° 旋转/镜像对称破缺：每个允许轨道取一个代表，分别作为分支
    reps = []
    for orbit in (P.S_SET, P.C_SET, P.L_SET):
        inter = set(offs) & set(orbit)
        if inter:
            reps.append(min(inter))
    t0 = time.time()
    for canon in reps:
        emb2 = Embedder(atoms, edges)
        emb2.pos[root] = (0, 0)
        emb2.occ.add((0, 0))
        emb2.pos[nb] = canon
        emb2.occ.add(canon)
        forb = emb2.check_midpoints(nb, canon)
        if forb is None:
            continue
        for m in forb:
            emb2.forbidden[m] += 1
        emb2.refresh()
        try:
            ok = emb2.dfs(budget)
        except TimeoutError:
            continue
        if ok:
            return {"ok": True, "nodes": emb2.nodes, "seconds": round(time.time() - t0, 1),
                    "place": dict(emb2.pos)}
    return {"ok": None if False else False, "nodes": 0, "seconds": round(time.time() - t0, 1)}


def main():
    cases = [
        ("T68", P.ORDER, [6, 2, 0, 24, 8, 8, 6, 6, 8]),
        ("T97", P.ORDER, [3, 8, 15, 10, 1, 0, 36, 22, 2]),
        ("T129", P.ORDER, [6, 12, 16, 13, 3, 0, 52, 24, 3]),
        ("T160", P.ORDER, [10, 20, 16, 15, 0, 1, 66, 30, 2]),
        ("OXKA154", ["O", "X", "K", "A"], [71, 35, 27, 28]),
    ]
    for name, elems, feed in cases:
        atoms = P.vec_to_atoms(tuple(feed), elems)
        mols = P.simulate(atoms)
        if not mols:
            print(name, "sim fail")
            continue
        big = max(mols, key=lambda m: len(m["atoms"]))
        r = embed2(big["atoms"], big["edges"], budget=2_000_000)
        print(f"{name}: n={len(big['atoms'])} -> ok={r['ok']} nodes={r['nodes']} {r['seconds']}s", flush=True)


if __name__ == "__main__":
    main()
