# -*- coding: utf-8 -*-
"""t15_forms_examples.py
找出「终态分子中的三价骨架形态」里不在 45 种骨架库（3+7+35）中的例子。
用法布尔：用 WL 颜色细化做带元素标签的多重图不变式，比较形态。
输出：t15_forms.json（新形态 + 例子分子 + 结构）
"""
import json
from collections import Counter, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}


def wl_key(atoms, edges):
    """atoms: list of element symbols; edges: list of (i,j,mult)
    WL 颜色细化 + 最终结构编码（带元素标签、多重键）。
    若整块只有一种三价元素，则把元素标签归一为 "A"（单类型模块与 O/P/K 无关）。"""
    n = len(atoms)
    if len(set(atoms)) == 1:
        atoms = ["A"] * n
    inc = [[] for _ in range(n)]
    for (i, j, m) in edges:
        inc[i].append((j, m))
        inc[j].append((i, m))
    colors = list(atoms)
    for _ in range(n + 1):
        sig = []
        for i in range(n):
            nb = tuple(sorted((m, colors[j]) for (j, m) in inc[i]))
            sig.append((colors[i], nb))
        uniq = sorted(set(sig))
        cmap = {s: k for k, s in enumerate(uniq)}
        new = [cmap[s] for s in sig]
        if new == colors:
            break
        colors = new
    # 最终 key：把颜色重新编号（按 (element,color) 排序）
    pairs = sorted((atoms[i], colors[i]) for i in range(n))
    nodes = {i: k for k, (i, _) in enumerate(sorted(((i, 0) for i in range(n)), key=lambda t: (atoms[t[0]], colors[t[0]])))}
    # 上面的 nodes 只是占位；改用排序后的索引
    order = sorted(range(n), key=lambda i: (atoms[i], colors[i]))
    idx = {i: k for k, i in enumerate(order)}
    es = sorted((min(idx[i], idx[j]), max(idx[i], idx[j]), m) for (i, j, m) in edges)
    return (n, tuple(atoms[i] for i in order), tuple(es))


def triv_components(rec):
    atoms = rec["atoms"]
    n = len(atoms)
    mult = [[0] * n for _ in range(n)]
    inc = [[] for _ in range(n)]
    for e in rec["edges"]:
        i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
        mult[i][j] += m
        mult[j][i] += m
        inc[i].append(j)
        inc[j].append(i)
    triv = [i for i in range(n) if atoms[i] in TRI]
    seen = set()
    out = []
    for s in triv:
        if s in seen:
            continue
        st = [s]
        seen.add(s)
        mem = [s]
        while st:
            u = st.pop()
            for v in inc[u]:
                if atoms[v] in TRI and v not in seen:
                    seen.add(v)
                    st.append(v)
                    mem.append(v)
        out.append(mem)
    return atoms, mult, out


def main():
    # 1) 45 库的 key
    lib = {}
    # 3 无三价：没有三价组件（不参与）
    # 7 单三价模块
    mod = {
        "单原子": ([("O", 1)], []),
        "单键二聚体": (["O", "O"], [(0, 1, 1)]),
        "双键二聚体": (["O", "O"], [(0, 1, 2)]),
        "三键二聚体": (["O", "O"], [(0, 1, 3)]),
        "三元链": (["O", "O", "O"], [(0, 1, 1), (1, 2, 1)]),
        "三元环(全单键)": (["O", "O", "O"], [(0, 1, 1), (1, 2, 1), (0, 2, 1)]),
        "三元环(含双键)": (["O", "O", "O"], [(0, 1, 1), (0, 2, 2), (1, 2, 1)]),
    }
    for name, (atoms, edges) in mod.items():
        lib[wl_key(atoms, edges)] = name
    # 35 多三价（T8 形态，去掉 3 个孤立单原子）
    t8 = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))
    n35 = 0
    for f in t8:
        if len(f["atoms"]) == 1:
            continue
        key = wl_key(f["atoms"], [tuple(e) for e in f["edges"]])
        lib.setdefault(key, "T8:" + f["formula"])
        n35 += 1
    print("库 key 数:", len(lib), "（T8 多原子形态", n35, "）")

    # 2) 扫描目录，找出不在库中的形态
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    newforms = {}
    count_by_tset = Counter()
    for rec in cat:
        atoms, mult, comps = triv_components(rec)
        for mem in comps:
            idx = {a: k for k, a in enumerate(mem)}
            ats = [atoms[a] for a in mem]
            es = []
            for a in range(len(mem)):
                for b in range(a + 1, len(mem)):
                    m = mult[mem[a]][mem[b]]
                    if m:
                        es.append((a, b, m))
            key = wl_key(ats, es)
            if key in lib:
                continue
            tset = "".join(sorted(set(ats)))
            count_by_tset[tset] += 1
            if key not in newforms:
                newforms[key] = {"atoms": ats, "edges": es, "n": len(ats),
                                 "tset": tset, "example": rec["formula"],
                                 "example_atoms": rec["atoms"],
                                 "component": mem,
                                 "record": rec}
    print("新形态总数:", len(newforms), " 按三价类型:", dict(count_by_tset))
    # 分布
    dist = Counter(v["n"] for v in newforms.values())
    print("按组件大小分布:", dict(sorted(dist.items())))
    # 保存（去掉大 record 里的 place 以减小体积）
    out = []
    for k, v in newforms.items():
        r = v["record"]
        out.append({"n": v["n"], "tset": v["tset"], "atoms": v["atoms"],
                    "edges": [list(e) for e in v["edges"]],
                    "example": v["example"],
                    "component": v["component"],
                    "molecule_atoms": r["atoms"],
                    "molecule_edges": [list(e) for e in r["edges"]],
                    "place": {str(kk): list(vv) for kk, vv in r["place"].items()} if r.get("place") else None})
    json.dump(out, open(BASE + r"\t15_forms.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print("saved t15_forms.json")
    # 打印示例：按大小排序，每类给几个
    out.sort(key=lambda x: (x["n"], x["tset"], x["example"]))
    shown = 0
    for x in out:
        if x["n"] <= 8:
            print(f"n={x['n']} [{x['tset']}] 例={x['example']} 骨架原子={''.join(x['atoms'])} 边={x['edges']}")
            shown += 1
            if shown >= 40:
                break


if __name__ == "__main__":
    main()
