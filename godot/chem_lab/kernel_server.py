# -*- coding: utf-8 -*-
"""ChemLab 内核服务：把 alchemy 的规则 1~11 / resolve / attrs / 三素 暴露给 Godot。

协议：TCP 127.0.0.1:8765，按行 JSON。
请求：{"id":1,"op":"molecule","formula":"CKF2"}
响应：{"id":1,"ok":true,"data":{...}}

只读内核，不修改 alchemy/ 下任何文件。
"""
import io
import json
import os
import socket
import sys
import time
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
sys.path.insert(0, ROOT)

import natural_engine as E  # noqa: E402
from alchemy import three_su as TS  # noqa: E402, F401
from alchemy import attrs as AT  # noqa: E402
from alchemy.core.elements import ORDER  # noqa: E402

CATALOG = {}
_F_CACHE = {}
_MOL_CACHE = {}


def load_catalog():
    global CATALOG
    path = os.path.join(ROOT, "t4_catalog_all_validated.json")
    t0 = time.time()
    recs = json.load(io.open(path, encoding="utf-8"))
    for r in recs:
        CATALOG.setdefault(r["formula"], r)
    print("[kernel] catalog %d formulas (%.1fs)" % (len(CATALOG), time.time() - t0),
          flush=True)


def parse_formula(f):
    """'C3K3F2' -> {'C':3,'K':3,'F':2}"""
    out = Counter()
    i = 0
    n = len(f)
    while i < n:
        ch = f[i]
        if ch not in ORDER:
            raise ValueError("bad formula %r" % f)
        i += 1
        num = ""
        while i < n and f[i].isdigit():
            num += f[i]
            i += 1
        out[ch] += int(num) if num else 1
    return out


def vec_of(comp):
    return [int(comp.get(e, 0)) for e in ORDER]


def comp_of_atoms(atoms):
    c = Counter()
    for a in atoms:
        c[a] += 1
    return c


def f_products(vec):
    key = tuple(vec)
    if key in _F_CACHE:
        return _F_CACHE[key]
    try:
        prods = E.complete_products(list(vec))
    except Exception:
        prods = None
    if prods:
        prods = [{"formula": p["formula"],
                  "atoms": list(p["atoms"]),
                  "edges": [list(e) for e in p["edges"]],
                  "vec": list(p["vec"]),
                  "c": p["c"]} for p in prods]
    _F_CACHE[key] = prods
    return prods


def molecule_info(f):
    if f in _MOL_CACHE:
        return _MOL_CACHE[f]
    rec = CATALOG.get(f)
    comp = parse_formula(f) if rec is None else comp_of_atoms(rec["atoms"])
    vec = vec_of(comp)
    if rec is not None:
        atoms = list(rec["atoms"])
        edges = [list(e) for e in rec["edges"]]
        place = rec.get("place")
    else:
        # 目录外产物：用 F 重建结构（稳定则单产物即自身）
        prods = f_products(vec)
        if prods and len(prods) == 1 and prods[0]["formula"] == f:
            atoms = prods[0]["atoms"]
            edges = prods[0]["edges"]
        else:
            atoms = []
            for e in ORDER:
                atoms.extend([e] * comp.get(e, 0))
            edges = []
        place = None
    attrs = AT.molecule_attrs(atoms, [tuple(e) for e in edges])
    prop = AT.property_of(attrs)
    try:
        k = max(1, len(AT.skeleton_units(atoms, [tuple(e) for e in edges])))
    except Exception:
        k = 1
    sc = TS.scores(comp)
    info = {
        "formula": f,
        "natoms": len(atoms),
        "comp": dict(comp),
        "vec": vec,
        "atoms": atoms,
        "edges": edges,
        "has_place": place is not None,
        "place": place if isinstance(place, (list, dict)) else None,
        "attrs": {"mass": round(attrs["mass"], 3),
                  "state": round(attrs["state"], 3),
                  "temperature": round(attrs["temperature"], 3)},
        "cell": prop["cell"],
        "grades": prop["grades"],
        "k": k,
        "A": round(sc["A"], 3),
        "D": round(sc["D"], 3),
        "ratt": sc["r_att"],
        "rrep": sc["r_rep"],
        "heat": int(comp.get("L", 0) + 2 * comp.get("F", 0)),
        "c": max(1, len(atoms) - 1),
    }
    _MOL_CACHE[f] = info
    return info


def mol_dict(f):
    info = molecule_info(f)
    return {"formula": f,
            "atoms": tuple(info["atoms"]),
            "edges": [tuple(e) for e in info["edges"]],
            "vec": list(info["vec"]),
            "c": info["c"],
            "label": f}


def op_molecule(req):
    return molecule_info(req["formula"])


def op_resolve(req):
    fs = [m["formula"] if isinstance(m, dict) else m for m in req["mols"]]
    T = float(req.get("T", 0.0))
    mols = [mol_dict(f) for f in fs]
    try:
        r = E.resolve(mols, T)
    except Exception as ex:
        return {"type": "none", "products": [], "error": str(ex),
                "csum": sum(m["c"] for m in mols)}
    prods = [p["formula"] for p in (r.get("products") or [])]
    return {"type": r.get("type"), "products": prods,
            "csum": r.get("csum"), "isum": r.get("isum"),
            "class": r.get("class"),
            "stages": len(r.get("stages") or [])}


def op_f(req):
    vec = [int(x) for x in req["vec"]]
    prods = f_products(vec)
    return {"products": prods, "ok": prods is not None}


def op_feed(req):
    """按元素子集 + IPF 生成投料：[{formula,count}, ...]"""
    elements = req.get("elements") or list(ORDER)
    n_mol = int(req.get("n_mol", 2000))
    natoms_min = int(req.get("natoms_min", 2))
    natoms_max = int(req.get("natoms_max", 8))
    pool = []
    for f, r in CATALOG.items():
        if not (natoms_min <= r["natoms"] <= natoms_max):
            continue
        comp = comp_of_atoms(r["atoms"])
        if any(e not in elements for e in comp):
            continue
        pool.append(f)
    if not pool:
        return {"feed": [], "pool": 0}
    # 目标：元素等份额；总原子数 ≈ n_mol * 平均 6.5
    total_atoms = n_mol * 6.5
    target = {e: total_atoms / float(len(elements)) for e in elements}
    vecs = {f: vec_of(comp_of_atoms(CATALOG[f]["atoms"])) for f in pool}
    w = {f: 1.0 for f in pool}
    for _ in range(60):
        tot = {e: 0.0 for e in elements}
        for f in pool:
            v = vecs[f]
            c = w[f]
            for e in elements:
                tot[e] += c * v[ORDER.index(e)]
        for f in pool:
            v = vecs[f]
            factor = 1.0
            for e in elements:
                if v[ORDER.index(e)] > 0 and tot[e] > 1e-9:
                    factor *= (target[e] / tot[e]) ** (v[ORDER.index(e)] / 3.0)
            w[f] *= factor
        # 归一化
        s = sum(w.values())
        if s <= 0:
            break
        scale = n_mol * 6.5 / max(1e-9, sum(w[f] * CATALOG[f]["natoms"] for f in pool))
        for f in pool:
            w[f] *= scale
            if w[f] < 1e-6:
                w[f] = 1e-6
    # 化成整数份数，总量 ≈ n_mol
    counts = {f: w[f] for f in pool}
    s = sum(counts.values())
    feed = []
    for f, c in sorted(counts.items(), key=lambda kv: -kv[1]):
        n = int(round(c * n_mol / s))
        if n > 0:
            feed.append({"formula": f, "count": n})
    return {"feed": feed, "pool": len(pool)}


HANDLERS = {"molecule": op_molecule, "resolve": op_resolve, "f": op_f,
            "feed": op_feed, "ping": lambda r: {"pong": True},
            "stats": lambda r: {"catalog": len(CATALOG), "f_cache": len(_F_CACHE),
                                "mol_cache": len(_MOL_CACHE)}}


def serve(port=8765):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(4)
    print("[kernel] listening on 127.0.0.1:%d" % port, flush=True)
    while True:
        conn, _ = srv.accept()
        fh = conn.makefile("rwb")
        try:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                t0 = time.time()
                try:
                    req = json.loads(line.decode("utf-8"))
                    if isinstance(req.get("args"), dict):
                        req.update(req["args"])
                    op = req.get("op", "")
                    h = HANDLERS.get(op)
                    if h is None:
                        resp = {"id": req.get("id"), "ok": False,
                                "error": "unknown op %r" % op}
                    else:
                        resp = {"id": req.get("id"), "ok": True,
                                "data": h(req)}
                except Exception as ex:
                    resp = {"id": None, "ok": False, "error": "%s: %s" % (
                        type(ex).__name__, ex)}
                resp["ms"] = round((time.time() - t0) * 1000, 2)
                fh.write((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
                fh.flush()
        except Exception as ex:
            print("[kernel] conn error:", ex, flush=True)
        finally:
            try:
                conn.close()
            except Exception:
                pass


def main():
    port = 8765
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    load_catalog()
    serve(port)


if __name__ == "__main__":
    main()
