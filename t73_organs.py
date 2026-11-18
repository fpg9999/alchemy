# -*- coding: utf-8 -*-
"""T73 器官形态的几何判定：器官在身体外缘还是内藏、受多少载荷、长了几根触肢，
据此从本族 4 种具体形态里选 1 种作为它实际长成的形态。
"""
import math

import t72_morphs as M

TAU = math.pi * 2
FAM_MORPHS = {k: [it[0] for it in v] for k, v in M.MORPHS.items()}

PICK = {
    "O": {"free": "spine", "free2": "cluster", "load": "column", "inner": "frame"},
    "P": {"free": "bladder", "free2": "sac", "load": "reservoir", "inner": "pump"},
    "K": {"free": "polybud", "free2": "split", "load": "gluepad", "inner": "pyramid"},
    "OP": {"free": "sucker", "free2": "wing", "load": "arch", "inner": "cpump"},
    "OK": {"free": "spike", "free2": "scale", "load": "shield", "inner": "socket"},
    "PK": {"free": "pulse", "free2": "ball", "load": "chamber", "inner": "rsac"},
    "OPK": {"free": "bud", "free2": "hypha", "load": "master", "inner": "ganglion"},
}


def _hull(pts):
    pts = sorted(set((round(x, 6), round(y, 6)) for x, y in pts))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo = []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    up = []
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def _on_hull(p, pts):
    if len(pts) <= 2:
        return True
    for i in range(len(pts)):
        p1, p2 = pts[i], pts[(i + 1) % len(pts)]
        cr = (p2[0] - p1[0]) * (p[1] - p1[1]) - (p2[1] - p1[1]) * (p[0] - p1[0])
        seg = math.hypot(p2[0] - p1[0], p2[1] - p1[1]) or 1.0
        if abs(cr) / seg < 1e-3:
            return True
    return False


def features(mol, bodies, polys, geoms, fusion, adj):
    """几何特征：是否在身体外缘 / 离中心多远 / 受多少载荷 / 长了几根触肢。"""
    n = len(bodies)
    cx = sum(b.cx for b in bodies) / max(1, n)
    cy = sum(b.cy for b in bodies) / max(1, n)
    hull = _hull([(b.cx, b.cy) for b in bodies])
    maxd = max(math.hypot(b.cx - cx, b.cy - cy) for b in bodies) or 1.0
    load = [0] * n
    for (ka, kb, fu) in fusion:
        load[ka] += 2
        load[kb] += 2
    skel_to_block = {}
    for i, b in enumerate(bodies):
        skel_to_block.setdefault(b.block["sk"], i)
    for br in mol.get("bridges", []):
        for sk in br.get("comps", []):
            k = skel_to_block.get(sk)
            if k is not None:
                load[k] += 1
    terms = [0] * n
    arms = [0] * n
    for m in geoms.get("mono", []):
        if m.get("kb") is not None:
            terms[m["kb"]] += 1
    for a in geoms.get("arms", []):
        if a.get("kb") is not None:
            arms[a["kb"]] += 1

    out = []
    for i, b in enumerate(bodies):
        radial = (b.cx - cx, b.cy - cy)
        d = math.hypot(*radial) or 1.0
        hf = _on_hull((b.cx, b.cy), hull)
        out.append({
            "k": i, "num": b.k + 1, "fam": b.key, "r": b.r,
            "on_hull": hf,
            "exposure": (d / maxd) if (hf and n > 1) else (0.0 if n > 1 else 1.0),
            "out_dir": (radial[0] / d, radial[1] / d),
            "load": load[i], "terms": terms[i], "arms": arms[i],
            "fused": any(i in fp for fp in fusion),
        })
    return out


def assign(feats):
    """按几何特征给每个器官配一种形态。"""
    out = []
    for f in feats:
        rule = PICK.get(f["fam"], PICK["OPK"])
        touch = f["terms"] + f["arms"]
        if f["load"] >= 2 or f["fused"]:
            m, why = rule["load"], "受力/融合→承力型"
        elif f["on_hull"] and touch >= 1:
            m, why = rule["free"], "外缘+触肢→感受/抓握型"
        elif f["on_hull"]:
            m, why = rule["free2"], "外缘→表面型"
        elif f["exposure"] <= 0.4:
            m, why = rule["inner"], "内藏→内脏型"
        else:
            m, why = rule["free2"], "半外露→过渡型"
        out.append(dict(f, morph=m, reason=why))
    return out


def analyze(mol, bodies, polys, geoms, fusion, adj):
    return assign(features(mol, bodies, polys, geoms, fusion, adj))
