# -*- coding: utf-8 -*-
"""T69 布局：骨架层级排版 + 块级几何体。

- 骨架（skeleton）= 若干 6 级块（block）组成；块之间若有 0 级同类三价键就是融合，
  在图上让两块贴边、接缝焊死。
- 骨架与骨架之间用二价桥连接（X 楔块 / W 肌腱 / A 薄膜）。
- 排版：先排骨架（力导向，节点少所以干净），再把骨架内的块贴边排成一行。
"""
import math
import random

import t68_shapes as S


CN = S.CN


def blocks_of(mol):
    out = []
    for sk in mol["skeletons"]:
        for b in sk["blocks"]:
            out.append({"sk": sk["num"], "mem": list(b["mem"]),
                        "formula": b["formula"], "lib": b.get("lib_formula"),
                        "in_lib": b.get("in_lib", True)})
    return out


def block_index(mol, blocks):
    idx_of = {}
    for k, b in enumerate(blocks):
        for i in b["mem"]:
            idx_of[i] = k
    return idx_of


def family_of(atoms):
    return S.fam_tint(atoms)


def body_radius(n):
    return 1.05 + 0.58 * math.sqrt(n)


class Body:
    def __init__(self, k, block, atoms):
        self.k = k
        self.block = block
        self.atoms = atoms
        self.n = len(atoms)
        self.key, self.col = family_of(atoms)
        self.kc = max(1, atoms.count("K"))
        self.r = body_radius(self.n)
        self.cx = 0.0
        self.cy = 0.0
        self.angle = 0.0

    def poly(self):
        rx = self.r * (1.06 if self.key not in ("O",) else 1.0)
        ry = self.r
        pts = S.fam_shape(self.key, self.cx, self.cy, rx, ry, self.kc)
        if abs(self.angle) < 1e-9:
            return pts
        c, s_ = math.cos(self.angle), math.sin(self.angle)
        return [(self.cx + (x - self.cx) * c - (y - self.cy) * s_,
                 self.cy + (x - self.cx) * s_ + (y - self.cy) * c) for (x, y) in pts]


class Skeleton:
    def __init__(self, num, blocks, bodies):
        self.num = num
        self.blocks = blocks
        self.bodies = bodies
        self.cx = 0.0
        self.cy = 0.0
        # 一行排列：半径 = 各块直径之和的一半 + 重叠修正
        self.r = max(b.r for b in bodies)
        if len(bodies) > 1:
            self.r = sum(b.r for b in bodies) * 0.70
        self.angle = 0.0

    def place_blocks(self):
        n = len(self.bodies)
        if n == 1:
            self.bodies[0].cx, self.bodies[0].cy = self.cx, self.cy
            self.bodies[0].angle = self.angle
            self.r = self.bodies[0].r
            return
        # 融合块：挨着排成一行，间隔 = rA+rB-0.56（边对边焊死）
        xs = [0.0]
        for i in range(1, n):
            prev, cur = self.bodies[i - 1], self.bodies[i]
            xs.append(xs[-1] + prev.r + cur.r - 0.56)
        xs = [x - (xs[-1] / 2.0) for x in xs]
        # 融合块的行方向与"父方向"垂直，避免骨架被拉长
        row_ang = self.angle + math.pi / 2.0
        ux, uy = math.cos(row_ang), math.sin(row_ang)
        for b, x in zip(self.bodies, xs):
            b.cx = self.cx + ux * x
            b.cy = self.cy + uy * x
            b.angle = row_ang
        self.r = max(abs(x) + b.r for x, b in zip(xs, self.bodies))


def initial_skeleton_positions(skel_list, mol, place):
    idx_of_num = {sk["num"]: sk["idx"] for sk in mol["skeletons"]}
    for sk in skel_list:
        pts = [place[i] for i in idx_of_num[sk.num]]
        sk.cx = sum(p[0] for p in pts) / float(len(pts))
        sk.cy = sum(p[1] for p in pts) / float(len(pts))
    mx = sum(sk.cx for sk in skel_list) / len(skel_list)
    my = sum(sk.cy for sk in skel_list) / len(skel_list)
    for sk in skel_list:
        sk.cx = (sk.cx - mx) * 0.75
        sk.cy = (sk.cy - my) * 0.75


def relax_skel(skel_list, springs, iters=1200):
    normal = [s for s in springs if s[3] != "rep"]
    rep = [s for s in springs if s[3] == "rep"]
    for _ in range(iters):
        for (i, j, rest, kind) in normal + rep:
            a, b = skel_list[i], skel_list[j]
            vx, vy = b.cx - a.cx, b.cy - a.cy
            d = math.hypot(vx, vy)
            if d < 1e-6:
                vx, vy, d = 1.0, 0.0, 1.0
            if kind == "rep" and d > rest:
                continue
            k = (d - rest) / d * 0.22
            a.cx += vx * k
            a.cy += vy * k
            b.cx -= vx * k
            b.cy -= vy * k


def separate_skel(skel_list, iters=500):
    n = len(skel_list)
    for _ in range(iters):
        for i in range(n):
            for j in range(i + 1, n):
                a, b = skel_list[i], skel_list[j]
                vx, vy = b.cx - a.cx, b.cy - a.cy
                d = math.hypot(vx, vy)
                need = a.r + b.r + 0.16
                if d >= need:
                    continue
                if d < 1e-6:
                    vx, vy, d = 1.0, 0.0, 1.0
                k = (need - d) / d * 0.5
                a.cx -= vx * k
                a.cy -= vy * k
                b.cx += vx * k
                b.cy += vy * k


def ordered_chain(atoms, adj):
    if len(atoms) <= 1:
        return list(atoms)
    st = set(atoms)
    ends = [a for a in atoms if len([b for b in adj.get(a, []) if b in st]) <= 1]
    if not ends:
        return list(atoms)
    out = [ends[0]]
    prev, cur = None, ends[0]
    while True:
        nxt = [b for b in adj.get(cur, []) if b in st and b != prev]
        if not nxt:
            break
        prev, cur = cur, nxt[0]
        out.append(cur)
    return out


def bridge_gap(elems):
    if len(elems) > 1:
        return 0.50 + 0.16 * len(elems)
    return {"X": 0.28, "W": 0.72, "A": 1.05}.get(elems[0] if elems else "", 1.0)


def build_layout(mol, box=None):
    blocks = blocks_of(mol)
    idx_of = block_index(mol, blocks)
    adj = {}
    for (a, b, m) in mol["edges"]:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    bodies = [Body(k, blk, [mol["atoms"][i] for i in blk["mem"]])
              for k, blk in enumerate(blocks)]
    by_sk = {}
    for b in bodies:
        by_sk.setdefault(b.block["sk"], []).append(b)
    skel_list = [Skeleton(num, [b.block for b in bs], bs) for num, bs in sorted(by_sk.items())]

    # 桥：按块对聚合，并记录骨架对
    bridge_items = []
    skel_of = {i: sk["num"] for sk in mol["skeletons"] for i in sk["idx"]}
    sym_springs = {}
    for br in mol["bridges"]:
        bidx = br["idx"]
        st = set(bidx)
        chain = ordered_chain(bidx, adj)
        ca = cb = None
        for end in (chain[0], chain[-1]):
            for y in adj.get(end, []):
                if y in st or y not in skel_of:
                    continue
                if ca is None:
                    ca = y
                elif y != ca:
                    cb = y
                    break
            if cb is not None:
                break
        if ca is None or cb is None:
            bridge_items.append({"br": br, "chain": chain, "ca": None, "cb": None,
                                 "elems": [mol["atoms"][i] for i in chain]})
            continue
        ka, kb = idx_of.get(ca), idx_of.get(cb)
        elems = [mol["atoms"][i] for i in chain]
        bridge_items.append({"br": br, "chain": chain, "ca": ca, "cb": cb,
                             "elems": elems, "ka": ka, "kb": kb})
        if ka is None or kb is None:
            continue
        sa, sb = bodies[ka].block["sk"], bodies[kb].block["sk"]
        if sa == sb:
            continue
        key = (min(sa, sb), max(sa, sb))
        g = bridge_gap(elems)
        sym_springs[key] = max(sym_springs.get(key, 0.0), g)

    # ---- 骨架排版：星形（枢纽骨架在中心，其余按桥辐射排开）
    adj_sk = {}
    for (sa, sb), g in sym_springs.items():
        adj_sk.setdefault(sa, {})[sb] = g
        adj_sk.setdefault(sb, {})[sa] = g
    by_num = {sk.num: sk for sk in skel_list}
    deg = {sk.num: len(adj_sk.get(sk.num, {})) for sk in skel_list}
    hub = max(skel_list, key=lambda sk: (deg[sk.num], sk.r))
    hub.cx, hub.cy, hub.angle = 0.0, 0.0, 0.0
    seen = set([hub.num])
    queue = [(hub, 0.0)]
    while queue:
        node, base_ang = queue.pop(0)
        kids = [n for n in adj_sk.get(node.num, {}) if n not in seen]
        kids.sort(key=lambda n: by_num[n].r, reverse=True)
        k = len(kids)
        for i, nchild in enumerate(kids):
            seen.add(nchild)
            child = by_num[nchild]
            if k == 1:
                ang = base_ang
            else:
                step = 1.15
                ang = base_ang + (i - (k - 1) / 2.0) * step
            gap = adj_sk[node.num].get(nchild, 1.2)
            dist = node.r + child.r + gap
            child.cx = node.cx + math.cos(ang) * dist
            child.cy = node.cy + math.sin(ang) * dist
            child.angle = ang
            queue.append((child, ang))
    rest = [sk for sk in skel_list if sk.num not in seen]
    base_r = max([sk.r for sk in seen and [by_num[n] for n in seen] or [2.0]])
    for i, sk in enumerate(rest):
        ang = 2 * math.pi * i / max(1, len(rest)) + 0.4
        sk.cx = math.cos(ang) * (base_r + sk.r + 1.5)
        sk.cy = math.sin(ang) * (base_r + sk.r + 1.5)
        sk.angle = 0.0
    # 平移到原点
    cx = sum(sk.cx for sk in skel_list) / len(skel_list)
    cy = sum(sk.cy for sk in skel_list) / len(skel_list)
    for sk in skel_list:
        sk.cx -= cx
        sk.cy -= cy
    separate_skel(skel_list, iters=260)
    for sk in skel_list:
        sk.place_blocks()

    fusion_pairs = []
    for sk in mol["skeletons"]:
        for fu in (sk.get("fusion") or []):
            ka, kb = idx_of.get(fu["a"]), idx_of.get(fu["b"])
            if ka is None or kb is None or ka == kb:
                continue
            fusion_pairs.append((ka, kb, fu))
    return bodies, bridge_items, fusion_pairs, idx_of, adj, skel_of
