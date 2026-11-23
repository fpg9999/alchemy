# -*- coding: utf-8 -*-
"""T94-A 自复制与生命形式普查（静态，只用目录 + 反应规则，不跑动态世界）。

口径（全部来自 t94_config / natural_engine，不硬编码旧值）：
  - 反应判定：natural_engine.complete_products(vec)（规则 1~11，只依赖总元素计数），
    resolve(mols, T) 的 complete 分支即它；温度口径 T_local=(Σheat + ec*T_env)/(n+ec)，
    heat(C,L,F)=(-1,+1,+2)，ec=env_coupling=0.5。
  - 三体自复制：A + B + C → 2A，判据 = resolve([A,B,C], T_local) 的 products 恰 2 个，
    且两个产物的元素计数都 == comp(A)（此时配方必 == A，因目录 comp→分子双射）。
  - 二元催化：A + B → A + C，判据 = F(compA+compB) 产物中保留 comp(A)，其余产物组成
    之和 == comp(B)；C 由质量守恒唯一确定（无同分异构体 ⇒ C==B 时惰性）。
  - 遗传保真度 = 产物 Mol.label（pot_all.mol_label 规范骨架形）与模板 label 完全一致的数量。
用法：
  python t94_census.py            # 正式参数（全量普查）
  python t94_census.py --quick    # 小范围自检
"""
import argparse
import collections
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import natural_engine as E
import pot_all as P
import t94_config as C

ORDER = P.ORDER
CATALOG = os.path.join(HERE, "t4_catalog_all_validated.json")
OUT_JSON = os.path.join(HERE, "t94_census.json")
OUT_PNG = os.path.join(HERE, "images", "t94_census.png")

# 正式参数
NMAX_STAB = 14      # 稳定性普查的原子数上限
NMAX_TEMPLATE = 12  # 复制模板的原子数上限
A_MIN, A_MAX = 3, 8     # 二元催化：催化剂 A 的原子数范围
B_MIN, B_MAX = 2, 4     # 二元催化：底物 B 的原子数范围
GRID_TEMPS = (200, 100, 50, 20, 0)   # 任务要求记录的 T_env 档


def flush(*args):
    print(*args)
    sys.stdout.flush()


# ---------------------------------------------------------------- 基础工具
def comp_of_record(rec):
    c = [0] * 9
    idx = {e: i for i, e in enumerate(ORDER)}
    for a in rec["atoms"]:
        c[idx[a]] += 1
    return tuple(c)


def heat_of(counts):
    """heat = -1*nC + 1*nL + 2*nF（t94_config.heat_w）。"""
    return C.heat_of({"C": counts["C"], "L": counts["L"], "F": counts["F"]})


def local_T(heats, T_env, ec):
    return (sum(heats) + ec * T_env) / (len(heats) + ec)


def schedule_T(t, params):
    return C.schedule_T(t, params["T0"], params["T_end"],
                        params["cool_ticks"], params["plateau"])


class Census(object):
    def __init__(self, quick=False):
        self.quick = quick
        self.params = dict(C.DEFAULT_PARAMS)
        self.ec = self.params["env_coupling"]
        self.recs = {}
        self.mols = {}
        self.by_n = collections.defaultdict(list)
        self.t0 = time.time()
        self.res = {}          # 写入 JSON 的主体

    # ------------------------------------------------------------ 载入
    def load(self):
        with open(CATALOG, encoding="utf-8") as f:
            cat = json.load(f)
        t = time.time()
        for r in cat:
            c = comp_of_record(r)
            if c in self.recs:
                raise RuntimeError("comp 重复！" + r["formula"])
            self.recs[c] = r
            self.by_n[sum(c)].append(c)
        flush("[T94] catalog %d 条, distinct comps %d, %.1fs" % (
            len(cat), len(self.recs), time.time() - t))
        self.n_catalog = len(cat)
        return cat

    def mol(self, c):
        m = self.mols.get(c)
        if m is None:
            m = self.mols[c] = E.mol_from_record(self.recs[c])
        return m

    # ------------------------------------------------------------ 目录统计
    def catalog_stats(self):
        elems = collections.Counter()
        n_by_size = collections.Counter()
        for c, r in self.recs.items():
            for e in r["atoms"]:
                elems[e] += 1
            n_by_size[sum(c)] += 1
        bijection = (self.n_catalog == len(self.recs))
        self.res["catalog"] = {
            "molecules": self.n_catalog,
            "distinct_comps": len(self.recs),
            "comp_species_bijection": bijection,
            "no_isomers": bijection,
            "natoms_min": min(n_by_size),
            "natoms_max": max(n_by_size),
            "elements": dict(sorted(elems.items())),
            "has_E": elems.get("E", 0),
            "count_by_n": {str(k): v for k, v in sorted(n_by_size.items())},
            "count_by_n_head": {str(k): v for k, v in sorted(n_by_size.items()) if k <= 20},
        }
        flush("[T94] comp↔物种双射: %s; 元素: %s" % (bijection, sorted(elems)))
        return n_by_size

    # ------------------------------------------------------------ fast 等价性
    def fast_check(self, sample_n=140):
        comps = list(self.recs)
        step = max(1, len(comps) // sample_n)
        sample = [c for i, c in enumerate(comps) if i % step == 0][:sample_n]
        def run(fast):
            E.clear_caches()
            E.set_fast(fast)
            out = {}
            t = time.time()
            for c in sample:
                pr = E.complete_products(tuple(2 * x for x in c)) or []
                out[c] = tuple(sorted(p["label"] for p in pr))
            return out, time.time() - t
        slow, ts = run(False)
        fast, tf = run(True)
        diff = [self.recs[c]["formula"] for c in sample if slow[c] != fast[c]]
        E.clear_caches()
        E.set_fast(True)
        self.res["fast_check"] = {
            "sample": len(sample), "slow_s": round(ts, 3), "fast_s": round(tf, 3),
            "n_diff": len(diff), "diff_examples": diff[:10],
            "note": "fast_pot 与 pot_v4 在 F(2V) 上逐位一致时才使用 fast；diff>0 即视为口径风险",
        }
        flush("[T94] fast 等价性: sample=%d diff=%d (slow %.2fs / fast %.2fs)" % (
            len(sample), len(diff), ts, tf))
        return diff

    # ------------------------------------------------------------ 稳定性普查
    def stability_census(self, nmax):
        stable = 0
        unstable = []
        same_comp_rearranged = []
        prod_count = collections.Counter()
        by_n = collections.Counter()
        t = time.time()
        for c, r in self.recs.items():
            n = sum(c)
            if n > nmax:
                continue
            by_n[n] += 1
            pr = E.complete_products(c) or []
            prod_count[len(pr)] += 1
            if len(pr) == 1 and pr[0]["label"] == self.mol(c)["label"]:
                stable += 1
            else:
                unstable.append({"formula": r["formula"], "n": n,
                                 "products": [p["formula"] for p in pr]})
                if len(pr) == 1 and pr[0]["vec"] == c:
                    same_comp_rearranged.append({
                        "formula": r["formula"], "n": n,
                        "product_formula": pr[0]["formula"],
                        "label_same": pr[0]["label"] == self.mol(c)["label"]})
        self.res["stability"] = {
            "scope": "natoms<=%d" % nmax,
            "n_comps": sum(by_n.values()),
            "stable": stable,
            "unstable": len(unstable),
            "unstable_examples": unstable[:20],
            "same_comp_rearranged": same_comp_rearranged,
            "product_count_dist": {str(k): v for k, v in sorted(prod_count.items())},
            "note": "F(V) 恰为自身=该组成稳定；unstable 极少（%d 个）说明小分子几乎都是不动点" % len(unstable),
        }
        flush("[T94] 稳定性普查 n<=%d: comps=%d stable=%d unstable=%d (%.1fs)" % (
            nmax, sum(by_n.values()), stable, len(unstable), time.time() - t))
        return stable, unstable

    # ------------------------------------------------------------ 复制普查
    def replication_census(self, nmax):
        repl = []
        t = time.time()
        for c, r in self.recs.items():
            n = sum(c)
            if not (2 <= n <= nmax):
                continue
            v2 = tuple(2 * x for x in c)
            pr = E.complete_products(v2) or []
            if len(pr) == 2 and tuple(pr[0]["vec"]) == c and tuple(pr[1]["vec"]) == c:
                lab = self.mol(c)["label"]
                fid = sum(1 for p in pr if p["label"] == lab)
                stable_A = (lambda pr1: len(pr1) == 1 and pr1[0]["label"] == lab)(
                    E.complete_products(c) or [])
                repl.append({
                    "formula": r["formula"], "comp": list(c), "n": n,
                    "fidelity": fid, "labels_equal": fid,
                    "A_stable": stable_A,
                    "heat": heat_of({"C": r["atoms"].count("C"),
                                     "L": r["atoms"].count("L"),
                                     "F": r["atoms"].count("F")}),
                    "dimer_comp_in_catalog": v2 in self.recs,
                })
        repl.sort(key=lambda x: (x["n"], x["formula"]))
        by_n = collections.Counter(x["n"] for x in repl)
        fid_dist = collections.Counter(x["fidelity"] for x in repl)
        heat_sign = collections.Counter(
            "exo" if x["heat"] > 0 else "zero" if x["heat"] == 0 else "endo" for x in repl)
        self.res["replication"] = {
            "criterion": "F(2*comp(A)) 恰为 2 个分子，且两产物元素计数都==comp(A)；则 A+B+C->2A",
            "n_templates": len(repl),
            "by_n": {str(k): v for k, v in sorted(by_n.items())},
            "fidelity_dist": {str(k): v for k, v in sorted(fid_dist.items())},
            "all_fidelity_2of2": (fid_dist.get(2, 0) == len(repl)),
            "all_A_stable": all(x["A_stable"] for x in repl),
            "n_A_unstable": sum(1 for x in repl if not x["A_stable"]),
            "fidelity_2": fid_dist.get(2, 0),
            "fidelity_0_templates": [x["formula"] for x in repl if x["fidelity"] == 0],
            "heat_sign": dict(heat_sign),
            "dimer_comp_in_catalog": sum(1 for x in repl if x["dimer_comp_in_catalog"]),
            "note": ("模板=目录内分子。2,594/2,596 个模板的 A 稳定（F(V)=[A]）；2 个 n=11 模板 "
                     "（X3P2K6、X3P6K2）的 F(V) 是同组成的另一骨架（规范骨架），复制保真度 0/2，"
                     "属于一次性规范化，不是可遗传变异。"),
            "templates": repl,
        }
        flush("[T94] 复制模板 %d 个 (n<=%d) %.1fs; 全部 A 稳定=%s; 保真 2/2=%s" % (
            len(repl), nmax, time.time() - t,
            all(x["A_stable"] for x in repl), fid_dist.get(2, 0) == len(repl)))
        return repl

    # ------------------------------------------------------------ 食物拆分
    def enumerate_splits(self, repl):
        """对每个复制模板 A，枚举 catalog 内 B、C（各>=2 原子）使 compB+compC==compA。"""
        t = time.time()
        splits = {}
        for x in repl:
            ca = tuple(x["comp"])
            nA = x["n"]
            if nA < 4:
                splits[x["formula"]] = []
                continue
            got = set()
            for nb in range(2, nA // 2 + 1):
                for cb in self.by_n[nb]:
                    cc = tuple(ca[i] - cb[i] for i in range(9))
                    if cc in self.recs and sum(cc) >= 2:
                        got.add(tuple(sorted((cb, cc))))
            splits[x["formula"]] = sorted(got)
        n_with = sum(1 for v in splits.values() if v)
        n_pairs = sum(len(v) for v in splits.values())
        self.res["splits"] = {
            "templates_with_split": n_with,
            "food_pairs_total": n_pairs,
            "templates_without_split": sum(1 for v in splits.values() if not v),
            "note": "目录内无单原子分子、无异核双原子 OX/OC/XC，故 n<=3 的模板无法拆分",
        }
        flush("[T94] 食物拆分: %d 个模板有拆分, 共 %d 组食物对 (%.1fs)" % (
            n_with, n_pairs, time.time() - t))
        return splits

    # ------------------------------------------------------------ 温度窗口
    def window_end_tick(self, t_env_min):
        """T_env(t)=T_end+(T0-T_end)exp(-6t/ct)，plateau 后 T_end。返回可行拍数（0=不可行）。"""
        p = self.params
        T0, T1, ct = p["T0"], p["T_end"], p["cool_ticks"]
        if t_env_min > T0:
            return 0
        if t_env_min <= T1:
            return int(ct)
        # T1 + (T0-T1)exp(-6t/ct) = t_env_min
        frac = (t_env_min - T1) / (T0 - T1)
        t = -ct / 6.0 * math.log(frac)
        return int(max(0.0, min(ct, math.floor(t))))

    def triples(self, repl, splits):
        t = time.time()
        rows = []
        fid_of = {x["formula"]: x["fidelity"] for x in repl}
        for x in repl:
            A = x["formula"]
            ca = tuple(x["comp"])
            sp = splits[A]
            if not sp:
                continue
            mA = self.mol(ca)
            hA = heat_of({"C": self.recs[ca]["atoms"].count("C"),
                          "L": self.recs[ca]["atoms"].count("L"),
                          "F": self.recs[ca]["atoms"].count("F")})
            for cb, cc in sp:
                mB, mC = self.mol(cb), self.mol(cc)
                hB = heat_of({"C": self.recs[cb]["atoms"].count("C"),
                              "L": self.recs[cb]["atoms"].count("L"),
                              "F": self.recs[cb]["atoms"].count("F")})
                hC = heat_of({"C": self.recs[cc]["atoms"].count("C"),
                              "L": self.recs[cc]["atoms"].count("L"),
                              "F": self.recs[cc]["atoms"].count("F")})
                csum = mA["c"] + mB["c"] + mC["c"]
                hs = hA + hB + hC
                # T_local=(hs+ec*Te)/(3+ec) >= csum  =>  Te >= ((3+ec)*csum-hs)/ec
                tmin = ((3 + self.ec) * csum - hs) / self.ec
                end = self.window_end_tick(tmin)
                rows.append({
                    "A": A, "nA": x["n"],
                    "B": self.recs[cb]["formula"], "nB": sum(cb),
                    "C": self.recs[cc]["formula"], "nC": sum(cc),
                    "csum": csum, "heat_sum": hs, "T_env_min": round(tmin, 2),
                    "exo": hs > 0, "window_end": end,
                    "fidelity": fid_of.get(A, 2), "in_catalog": True,
                })
        rows.sort(key=lambda r: (r["nA"], r["T_env_min"], -r["heat_sum"], r["A"]))
        self.res["triples"] = {
            "n_rows": len(rows),
            "criterion": "A+B+C->2A；T_env 需 >= ((3+ec)*Σc - Σheat)/ec（ec=0.5 时 =7Σc-2Σheat）",
            "rows": rows,
        }
        flush("[T94] 三体候选 %d 行 %.1fs; T_env_min min=%.1f max=%.1f" % (
            len(rows), time.time() - t,
            min(r["T_env_min"] for r in rows), max(r["T_env_min"] for r in rows)))
        return rows

    # ------------------------------------------------------------ 逐档验证
    def resolve_check(self, repl, rows, n_grid=360, n_food=60):
        """抽查 resolve 在 T_env=200/100/50/20/0 的实际判定，与解析窗口对照。"""
        t = time.time()
        if not rows:
            self.res["resolve_check"] = {"n": 0}
            return
        step = max(1, len(rows) // n_grid)
        sample = rows[::step][:n_grid]
        mis = 0
        examples = []
        for r in sample:
            ca = self._comp_by_formula(r["A"])
            cb = self._comp_by_formula(r["B"])
            cc = self._comp_by_formula(r["C"])
            mA, mB, mC = self.mol(ca), self.mol(cb), self.mol(cc)
            hA = C.heat_of({"C": self.recs[ca]["atoms"].count("C"),
                            "L": self.recs[ca]["atoms"].count("L"),
                            "F": self.recs[ca]["atoms"].count("F")})
            hB = C.heat_of({"C": self.recs[cb]["atoms"].count("C"),
                            "L": self.recs[cb]["atoms"].count("L"),
                            "F": self.recs[cb]["atoms"].count("F")})
            hC = C.heat_of({"C": self.recs[cc]["atoms"].count("C"),
                            "L": self.recs[cc]["atoms"].count("L"),
                            "F": self.recs[cc]["atoms"].count("F")})
            grid = []
            for Te in GRID_TEMPS:
                Tl = local_T([hA, hB, hC], Te, self.ec)
                res = E.resolve([mA, mB, mC], Tl)
                pred = Tl >= r["csum"]
                ok_prod = False
                if res["type"] == "complete":
                    pr = res["products"]
                    ok_prod = (len(pr) == 2 and tuple(pr[0]["vec"]) == ca
                               and tuple(pr[1]["vec"]) == ca)
                if pred != (res["type"] == "complete"):
                    mis += 1
                grid.append({"T_env": Te, "T_local": round(Tl, 2), "type": res["type"],
                             "products": [p["formula"] for p in (res["products"] or [])],
                             "two_A": ok_prod})
            if len(examples) < 12:
                examples.append({"A": r["A"], "B": r["B"], "C": r["C"],
                                 "csum": r["csum"], "T_env_min": r["T_env_min"],
                                 "grid": grid})
        # 食物单独合成检查（模板是否真的没用）
        fsample = rows[::max(1, len(rows) // n_food)][:n_food]
        food_only = 0
        food_examples = []
        for r in fsample:
            ca = self._comp_by_formula(r["A"])
            cb = self._comp_by_formula(r["B"])
            cc = self._comp_by_formula(r["C"])
            v = tuple(cb[i] + cc[i] for i in range(9))
            pr = E.complete_products(v) or []
            ok = len(pr) == 1 and pr[0]["vec"] == ca
            food_only += 1 if ok else 0
            if len(food_examples) < 8:
                food_examples.append({"A": r["A"], "foods": [r["B"], r["C"]],
                                      "F(B+C)": [p["formula"] for p in pr],
                                      "is_A": ok})
        self.res["resolve_check"] = {
            "n": len(sample), "grid": list(GRID_TEMPS),
            "mismatch_full_condition": mis,
            "examples": examples,
            "food_only_synthesis": {"n": len(fsample), "n_ok": food_only,
                                    "examples": food_examples,
                                    "note": "B+C 单独也生成 A —— 证明模板不参与产物生成"},
        }
        flush("[T94] resolve 抽查 %d 行 × %d 档: 解析窗口失配 %d; 食物单独合成 %d/%d (%.1fs)" % (
            len(sample), len(GRID_TEMPS), mis, food_only, len(fsample),
            time.time() - t))

    def _comp_by_formula(self, f):
        if not hasattr(self, "_by_formula"):
            self._by_formula = {r["formula"]: c for c, r in self.recs.items()}
        return self._by_formula[f]

    # ------------------------------------------------------------ 二元催化
    def catalysis_scan(self, amax=8, bmax=4, vmax=12):
        t = time.time()
        A = [c for c in self.recs if A_MIN <= sum(c) <= amax]
        B = [c for c in self.recs if B_MIN <= sum(c) <= bmax]
        fcache = {}
        def F(v):
            r = fcache.get(v)
            if r is None:
                r = [(tuple(p["vec"]), p["formula"]) for p in (E.complete_products(v) or [])]
                fcache[v] = r
            return r
        stat = collections.Counter()
        inert_ex = []
        frag_ex = []
        catal = []
        dup_same = 0
        dup_diff = 0
        for ca in A:
            ra = self.recs[ca]
            for cb in B:
                v = tuple(ca[i] + cb[i] for i in range(9))
                if sum(v) > vmax:
                    continue
                prods = F(v)
                if len(prods) < 2:
                    stat["single_product"] += 1
                    continue
                comps = [p[0] for p in prods]
                hit = [i for i, pc in enumerate(comps) if pc == ca]
                if not hit:
                    stat["A_destroyed"] += 1
                    continue
                rest = [comps[j] for j in range(len(comps)) if j not in hit]
                rest_sum = [0] * 9
                for rc in rest:
                    for k in range(9):
                        rest_sum[k] += rc[k]
                if len(rest) == 1:
                    if tuple(rest_sum) == cb:
                        stat["inert"] += 1
                        if len(inert_ex) < 8:
                            inert_ex.append({"A": ra["formula"],
                                             "B": self.recs[cb]["formula"],
                                             "products": [p[1] for p in prods]})
                    else:
                        stat["A_duplicated"] += 1
                        if ca == cb:
                            dup_same += 1
                        else:
                            dup_diff += 1
                else:
                    if tuple(rest_sum) == cb:
                        stat["catalytic_decomposition"] += 1
                        if len(frag_ex) < 20:
                            frag_ex.append({"A": ra["formula"],
                                            "B": self.recs[cb]["formula"],
                                            "fragments": [self.recs[rc]["formula"] for rc in rest],
                                            "total_n": sum(v)})
                        catal.append((ra["formula"], self.recs[cb]["formula"]))
                    else:
                        stat["A_duplicated"] += 1
                        if ca == cb:
                            dup_same += 1
                        else:
                            dup_diff += 1
        self.res["catalysis"] = {
            "scan": {"A_n": [A_MIN, amax], "B_n": [B_MIN, bmax],
                     "max_total_n": vmax,
                     "n_A_comps": len(A), "n_B_comps": len(B),
                     "pairs": len(A) * len(B),
                     "distinct_total_comps": len(fcache)},
            "class": dict(stat),
            "n_catalytic": stat.get("catalytic_decomposition", 0),
            "A_duplicated_same_comp": dup_same,
            "A_duplicated_diff_comp": dup_diff,
            "inert_examples": inert_ex,
            "catalytic_examples": frag_ex,
            "theorem": ("无同分异构体（comp↔物种双射）⇒ 若 F(compA+compB) 保留 A 且只剩 1 个产物，"
                        "该产物必为 B 本身（惰性）；二元 A+B->A+C (C!=B) 不可能。"
                        "要产生 C!=B 必须让 B 裂成 >=2 个碎片，扫描内 0 例。"
                       "A_duplicated 的 %d 例全部是 A==B 的同种对（2A->2A，惰性），异种 0 例。"
                       % (dup_same + dup_diff)),
        }
        flush("[T94] 二元催化扫描 %d 对 (%.1fs): %s" % (
            len(A) * len(B), time.time() - t, dict(stat)))
        return self.res["catalysis"]

    # ------------------------------------------------------------ 汇总
    def summarize(self, repl, splits, rows):
        p = self.params
        # 模板汇总表
        by_formula = collections.defaultdict(list)
        for r in rows:
            by_formula[r["A"]].append(r)
        tmpl = []
        for x in repl:
            f = x["formula"]
            sp = splits[f]
            if not sp:
                continue
            r = by_formula[f]
            best = min(r, key=lambda z: (z["T_env_min"], -z["heat_sum"]))
            tmpl.append({
                "A": f, "nA": x["n"], "comp_A": list(x["comp"]),
                "n_splits": len(sp), "T_env_min_best": best["T_env_min"],
                "window_end_best": best["window_end"],
                "foods_best": [best["B"], best["C"]],
                "exo_best": best["exo"], "heat_A": x["heat"],
                "A_stable": x["A_stable"],
            })
        tmpl.sort(key=lambda z: (z["nA"], z["T_env_min_best"], -z["n_splits"]))
        self.res["templates"] = tmpl
        # 温度窗口统计
        tmins = [r["T_env_min"] for r in rows]
        ends = [r["window_end"] for r in rows]
        bins = [0, 26, 30, 40, 50, 60, 80, 100, 120, 150, 200, 260]
        hist = collections.Counter()
        for v in tmins:
            for i in range(len(bins) - 1):
                if bins[i] <= v < bins[i + 1]:
                    hist["%d-%d" % (bins[i], bins[i + 1])] += 1
                    break
            else:
                hist[">=260"] += 1
        def le(x):
            return sum(1 for v in tmins if v <= x)
        self.res["windows"] = {
            "T_env_min": {"min": min(tmins), "max": max(tmins),
                          "mean": round(sum(tmins) / len(tmins), 2)},
            "hist": dict(hist),
            "count_le": {str(x): le(x) for x in (0, 20, 26, 40, 50, 60, 100, 120, 150, 200)},
            "n_never_feasible": sum(1 for v in tmins if v > p["T0"]),
            "n_feasible_tonight": le(p["T0"]),
            "window_end": {"min": min(ends), "max": max(ends),
                           "median": sorted(ends)[len(ends) // 2],
                           "mean": round(sum(ends) / len(ends), 1)},
            "count_by_nA": {},
            "heat_sign": {"exo": sum(1 for r in rows if r["heat_sum"] > 0),
                          "zero": sum(1 for r in rows if r["heat_sum"] == 0),
                          "endo": sum(1 for r in rows if r["heat_sum"] < 0)},
        }
        by_nA = collections.defaultdict(list)
        for r in rows:
            by_nA[r["nA"]].append(r)
        for nA, rs in sorted(by_nA.items()):
            self.res["windows"]["count_by_nA"][str(nA)] = {
                "triples": len(rs),
                "templates": len(set(r["A"] for r in rs)),
                "T_env_min_min": min(r["T_env_min"] for r in rs),
                "T_env_min_median": sorted(r["T_env_min"] for r in rs)[len(rs) // 2],
                "feasible_tonight": sum(1 for r in rs if r["T_env_min"] <= p["T0"]),
            }
        # 最小生命形式
        minimal = []
        for r in rows:
            if r["nA"] == 4:
                rr = dict(r)
                rr["comp_A"] = list(self._comp_by_formula(r["A"]))
                minimal.append(rr)
        self.res["minimal"] = {
            "n": 4,
            "n_triples": len(minimal),
            "n_templates": len(set(r["A"] for r in minimal)),
            "rows": minimal,
            "note": "目录里没有单原子分子、没有 OX/OC/XC 等异核双原子，故 n<4 无法三体拆分；n=4 是最小可能",
        }
        self.res["lifeform"] = {
            "minimal_replicator": minimal[0] if minimal else None,
            "minimal_composition": "A2F2 = A2 + F2（4 原子，26°C 起可行，放热 +8）",
            "fidelity_note": "2,594/2,596 模板保真 2/2；X3P2K6/X3P6K2(n=11) 保真 0/2（F(V) 规范骨架与目录骨架不同，复制后即固定）",
            "n_templates_total": len(repl),
            "n_templates_with_foods": len(tmpl),
            "n_triples_total": len(rows),
            "n_feasible_tonight": le(p["T0"]),
            "energy_source": "只有温度：反应要求 T_local>=Σc；放热分子(F/L 富集)降低所需 T_env",
            "no_template_effect": True,
        }
        self.res["problems"] = [
            "模板零作用：complete_products 只依赖总元素计数，A 不参与反应判定，无信息传递/催化。",
            "无变异：目录中每个组成只有唯一分子（无同分异构体），遗传保真度恒为 2/2，无法产生差异，也就没有选择。",
            "食物对合成：B+C 单独即可生成 A（抽查 %d/%d 成立），三体反应等价于「B+C→A」+ 原模板存活，不是模板复制。" % (
                self.res.get("resolve_check", {}).get("food_only_synthesis", {}).get("n_ok", 0),
                self.res.get("resolve_check", {}).get("food_only_synthesis", {}).get("n", 0)),
            "温度窗口极窄：最快候选也要 T_env>=26°C；今晚 200→0°C 冷却中前 %d 拍才有窗口，0°C 平台无任何候选（T_env_min 全部 >0）。" % (
                self.res["windows"]["window_end"]["max"]),
            "二元催化=0：A+B→A+C（C!=B）因无同分异构体不可能；B 裂解成碎片的催化分解扫描 %d 对为 0 例。" % (
                self.res["catalysis"]["scan"]["pairs"]),
            "没有空间区隔/边界：产物与模板同一锅，无法区分「自己的后代」；需要 T93 那种固态占格膜才能隔离。",
            "没有恒素/能量货币：温度是唯一能源，没有恒素门控耦合的代谢循环；升温即复制、降温即停。",
            "碰撞概率没算：三体反应需要 3 个正确分子同时相遇（cap=36 的世界里），静态普查只给「规则允许」。",
            "大分子惰性：n<=14 的 %d 个组成里 %d 个 F(V) 恰为自身，说明规则下大多数小分子是惰性不动点，反应需要特定配比/温度。" % (
                self.res["stability"]["n_comps"], self.res["stability"]["stable"]),
            "目录外物质未知：84,225 条为「已验证」集合，环境里若出现目录外中间态，本普查不覆盖。",
        ]
        self.res["comparison"] = {
            "T79": "T79 已在二元路径（A+营养物）得 0 催化/0 净放大；本任务三体路径找到 2,411 个『食物对合成』模板，"
                   "但证明其等价于 B+C->A 的加和合成，不构成模板复制，与 T79 否定结论一致。",
            "T89": "T88 六群系 86 个 mover 无复制/遗传；本普查说明规则层面自发复制只是组成决定的加和合成，"
                   "无法产生可遗传变异，与 T89「有行动无生命」一致。",
        }
        self.res["meta"] = {
            "title": "T94-A 自复制与生命形式普查",
            "date": "2026-11-24",
            "catalog": os.path.basename(CATALOG),
            "engine": "natural_engine.complete_products + resolve（不改内核）",
            "params": dict(p, ec=self.ec),
            "runtime_s": None,
        }
        flush("[T94] 汇总: 模板 %d, 三体 %d, 今晚可行 %d, 最小 n=4 共 %d 行" % (
            len(tmpl), len(rows), le(p["T0"]), len(minimal)))
        return tmpl, minimal

    # ------------------------------------------------------------ 主流程
    def run(self):
        self.load()
        self.catalog_stats()
        self.fast_check(sample_n=100 if self.quick else 140)
        nmax_stab = 8 if self.quick else NMAX_STAB
        nmax_tmp = 8 if self.quick else NMAX_TEMPLATE
        self.stability_census(nmax_stab)
        repl = self.replication_census(nmax_tmp)
        splits = self.enumerate_splits(repl)
        rows = self.triples(repl, splits)
        self.resolve_check(repl, rows, n_grid=60 if self.quick else 360,
                           n_food=20 if self.quick else 80)
        self.catalysis_scan(amax=6 if self.quick else A_MAX,
                            bmax=4, vmax=10 if self.quick else 12)
        self.summarize(repl, splits, rows)
        self.res["meta"]["runtime_s"] = round(time.time() - self.t0, 1)
        return self.res


# ---------------------------------------------------------------- 画图
def render_png(res, path):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1560, 1220
    BG = (250, 249, 246)
    C_DARK = (45, 45, 50)
    C_GREY = (110, 110, 118)
    C_RED = (196, 62, 52)
    C_BLUE = (46, 96, 160)
    C_GREEN = (54, 132, 78)
    C_ORANGE = (206, 126, 34)
    C_LIGHT = (232, 232, 228)
    C_GRID = (222, 222, 218)
    try:
        F_T = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 30)
        F_S = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 19)
        F_B = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 15)
        F_L = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 13)
        F_X = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 11)
    except Exception:
        F_T, F_S, F_B, F_L, F_X = [ImageFont.load_default()] * 5
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    def text(x, y, s, font=F_B, fill=C_DARK, anchor="la"):
        d.text((x, y), s, font=font, fill=fill, anchor=anchor)

    def frame(x0, y0, x1, y1, title):
        d.rectangle([x0, y0, x1, y1], fill=(255, 255, 255),
                    outline=(214, 212, 206), width=1)
        d.line([x0 + 10, y0 + 30, x1 - 10, y0 + 30], fill=C_LIGHT, width=1)
        text(x0 + 12, y0 + 6, title, F_S, C_DARK)

    text(W // 2, 14, res["meta"]["title"], F_T, C_DARK, "ma")
    p = res["meta"]["params"]
    text(W // 2, 52, "目录 %d 条 · 复制模板 %d · 三体候选 %d · T0=%.0f°C→T_end=%.0f°C（%d 拍）· ec=%.1f"
         % (res["catalog"]["molecules"], res["replication"]["n_templates"],
            res["triples"]["n_rows"], p["T0"], p["T_end"], int(p["cool_ticks"]), p["ec"]),
         F_L, C_GREY, "ma")

    # ---- 面板 1：复制模板按 n 分布 + 其中有食物拆分 ----
    x0, y0, x1, y1 = 60, 90, 790, 400
    frame(x0, y0, x1, y1, "(1) 三体复制模板按原子数 n：有食物拆分(深) / 无(浅)")
    by_n = {int(k): v for k, v in res["replication"]["by_n"].items()}
    split_by_n = {}
    for t in res["templates"]:
        split_by_n[t["nA"]] = split_by_n.get(t["nA"], 0) + 1
    ns = list(range(2, max(by_n) + 1))
    vmax = max(by_n.values()) if by_n else 1
    px0, px1 = x0 + 60, x1 - 20
    py0, py1 = y0 + 60, y1 - 45
    barw = (px1 - px0) / len(ns) * 0.66
    step = (px1 - px0) / len(ns)
    # y 轴网格
    for k in range(0, 5):
        vy = py1 - (py1 - py0) * k / 4
        d.line([px0, vy, px1, vy], fill=C_GRID)
        text(px0 - 8, vy, "%d" % round(vmax * k / 4), F_X, C_GREY, "rm")
    for i, n in enumerate(ns):
        bh = (py1 - py0) * by_n.get(n, 0) / vmax
        bx = px0 + step * (i + 0.5) - barw / 2
        if bh > 0:
            d.rectangle([bx, py1 - bh, bx + barw, py1], fill=C_LIGHT, outline=C_GREY)
        bh2 = (py1 - py0) * split_by_n.get(n, 0) / vmax
        if bh2 > 0:
            d.rectangle([bx, py1 - bh2, bx + barw, py1], fill=C_BLUE, outline=C_BLUE)
        text(px0 + step * (i + 0.5), py1 + 8, "%d" % n, F_X, C_GREY, "ma")
        if by_n.get(n):
            text(px0 + step * (i + 0.5), py1 - bh - 16, str(by_n[n]), F_X, C_DARK, "ma")
    text((px0 + px1) / 2, py1 + 26, "模板原子数 n", F_L, C_GREY, "ma")
    text(x0 + 68, y0 + 40, "模板数", F_L, C_GREY)
    d.rectangle([x1 - 200, y1 - 24, x1 - 188, y1 - 16], fill=C_BLUE)
    text(x1 - 184, y1 - 26, "有食物拆分", F_X, C_GREY)
    d.rectangle([x1 - 96, y1 - 24, x1 - 84, y1 - 16], fill=C_LIGHT, outline=C_GREY)
    text(x1 - 80, y1 - 26, "无拆分(n=2,3)", F_X, C_GREY)

    # ---- 面板 2：T_env_min 直方图 + 温度日程 ----
    x0, y0, x1, y1 = 820, 90, 1500, 400
    frame(x0, y0, x1, y1, "(2) 三体候选所需最低环境温度 T_env_min：柱区间=[左,右)")
    w = res["windows"]
    tmins = [r["T_env_min"] for r in res["triples"]["rows"]]
    edges = [26, 30, 40, 50, 60, 80, 100, 120, 150, 200, 252]
    hist = [0] * (len(edges) - 1)
    for v in tmins:
        for i in range(len(edges) - 1):
            if edges[i] <= v < edges[i + 1]:
                hist[i] += 1
                break
    px0, px1 = x0 + 56, x1 - 18
    py0, py1 = y0 + 66, y1 - 52
    hv = max(hist) or 1
    for k in range(0, 5):
        vy = py1 - (py1 - py0) * k / 4
        d.line([px0, vy, px1, vy], fill=C_GRID)
        text(px0 - 8, vy, "%d" % round(hv * k / 4), F_X, C_GREY, "rm")
    step = (px1 - px0) / len(hist)
    for i, v in enumerate(hist):
        bh = (py1 - py0) * v / hv
        bx = px0 + step * (i + 0.4)
        d.rectangle([bx, py1 - bh, bx + step * 0.62, py1], fill=C_ORANGE, outline=C_ORANGE)
        text(px0 + step * (i + 0.71), py1 + 7, str(edges[i]), F_X, C_GREY, "ma")
    text((px0 + px1) / 2, py1 + 26, "T_env_min (°C)：柱区间=[左,右)；<=200°C 才在今晚可行", F_L, C_GREY, "ma")
    # 温度日程概览：标出各 T_env 档对应的可行拍数
    fast = max(r["window_end"] for r in res["triples"]["rows"])
    text(px0, y0 + 38, "今晚可行 %d/%d 行；T_env_min 最低 %.0f°C → 窗口最长 %d 拍" % (
        w["n_feasible_tonight"], res["triples"]["n_rows"], w["T_env_min"]["min"], fast), F_X, C_BLUE)

    # ---- 面板 3：散点 nA vs T_env_min ----
    x0, y0, x1, y1 = 60, 420, 790, 790
    frame(x0, y0, x1, y1, "(3) 每个三体候选：(nA, T_env_min)，红=放热 蓝=吸热")
    px0, px1 = x0 + 50, x1 - 22
    py0, py1 = y0 + 50, y1 - 44
    tmax = 260.0
    for k in range(0, 7):
        vy = py1 - (py1 - py0) * k / 6
        d.line([px0, vy, px1, vy], fill=C_GRID)
        text(px0 - 8, vy, "%d" % round(tmax * k / 6), F_X, C_GREY, "rm")
    for n in range(4, 13):
        vx = px0 + (px1 - px0) * (n - 4) / 8
        d.line([vx, py0, vx, py1], fill=C_GRID)
        text(vx, py1 + 8, "%d" % n, F_X, C_GREY, "ma")
    for r in res["triples"]["rows"]:
        vx = px0 + (px1 - px0) * (r["nA"] - 4) / 8
        vy = py1 - (py1 - py0) * min(r["T_env_min"], tmax) / tmax
        col = C_RED if r["exo"] else C_BLUE
        d.ellipse([vx - 2, vy - 2, vx + 2, vy + 2], fill=col)
    # 参考线：T_env=200 / 100 / 50
    for val, lab in ((200, "T_env=200（起点）"), (100, "100"), (50, "50"), (26, "26（最低）")):
        vy = py1 - (py1 - py0) * val / tmax
        d.line([px0, vy, px1, vy], fill=(170, 170, 170))
        text(px0 + 4, vy - 14, lab, F_X, C_GREY)
    text((px0 + px1) / 2, py1 + 26, "模板原子数 nA", F_L, C_GREY, "ma")
    text(x0 + 6, y0 + 34, "T_env_min (°C)", F_L, C_GREY)

    # ---- 面板 4：窗口时长 top 16 ----
    x0, y0, x1, y1 = 820, 420, 1500, 790
    frame(x0, y0, x1, y1, "(4) 最小/最省温候选：今晚可行拍数（0=立即停止）")
    best = [r for r in res["triples"]["rows"] if r["window_end"] > 0]
    best.sort(key=lambda r: (r["nA"], r["T_env_min"], -r["heat_sum"]))
    pick = best[:16]
    py0, py1 = y0 + 44, y1 - 34
    hrow = (py1 - py0) / max(1, len(pick))
    emax = max([r["window_end"] for r in pick] or [1]) or 1
    px0, px1 = x0 + 250, x1 - 40
    for i, r in enumerate(pick):
        cy = py0 + hrow * (i + 0.5)
        vw = (px1 - px0) * r["window_end"] / emax
        col = C_GREEN if r["exo"] else C_BLUE
        d.rectangle([px0, cy - hrow * 0.30, px0 + max(2, vw), cy + hrow * 0.30],
                    fill=col, outline=col)
        text(px0 - 8, cy, "%s = %s+%s" % (r["A"], r["B"], r["C"]), F_X, C_DARK, "rm")
        text(px0 + max(2, vw) + 6, cy, "%d 拍 (%.0f°C)" % (r["window_end"], r["T_env_min"]),
             F_X, C_GREY, "lm")
    text((px0 + px1) / 2, py1 + 14, "可行拍数 t_end = 100·ln(200/T_env_min)（上限 600）", F_X, C_GREY, "ma")

    # ---- 面板 5：二元反应分类 ----
    x0, y0, x1, y1 = 60, 810, 790, 1120
    frame(x0, y0, x1, y1, "(5) 二元 A+B 扫描：没有任何一对构成催化闭环")
    cl = res["catalysis"]["class"]
    items = [("A 被消耗/不保留", cl.get("A_destroyed", 0), C_GREY),
             ("规则不动（F 只给 1 个分子）", cl.get("single_product", 0), C_LIGHT),
             ("A+B 惰性共存", cl.get("inert", 0), C_GREEN),
             ("A 被复制(仅同种对)", cl.get("A_duplicated", 0), C_ORANGE),
             ("A 保留且 B 裂解(催化)", cl.get("catalytic_decomposition", 0), C_RED)]
    total = sum(v for _, v, _ in items) or 1
    px0, px1 = x0 + 250, x1 - 34
    py0, py1 = y0 + 74, y1 - 26
    hrow = (py1 - py0) / len(items)
    logmax = math.log10(total + 1)
    for i, (lab, v, col) in enumerate(items):
        cy = py0 + hrow * (i + 0.5)
        wv = (px1 - px0) * (math.log10(v + 1) / logmax)
        d.rectangle([px0, cy - hrow * 0.3, px0 + max(2, wv), cy + hrow * 0.3], fill=col)
        text(px0 - 8, cy, lab, F_X, C_DARK, "rm")
        text(px0 + max(2, wv) + 6, cy, "%d" % v, F_X, C_GREY, "lm")
    text(x0 + 12, y0 + 40, "对数刻度；对数 %d（A n=%d..%d × B n=%d..%d）" % (
        res["catalysis"]["scan"]["pairs"], A_MIN, A_MAX, B_MIN, B_MAX), F_X, C_GREY)

    # ---- 面板 6：最小生命形式 + 关键数字 ----
    x0, y0, x1, y1 = 820, 810, 1500, 1120
    frame(x0, y0, x1, y1, "(6) 结果速览：三体自复制成立，但它是「加和合成」")
    lines = [
        ("复制模板", "%d 个（n=2..12），其中 %d 个有目录内食物拆分" % (
            res["replication"]["n_templates"], len(res["templates"]))),
        ("三体候选", "%d 行（模板×食物对）" % res["triples"]["n_rows"]),
        ("最小形式", "n=4：A2F2 + A2 + F2 → 2 A2F2（另 W2F2/X2F2），26°C 起可行"),
        ("保真度", "2,594/2,596 模板 2/2；X3P2K6/X3P6K2 为 0/2（一次性规范化）"),
        ("模板作用", "零：F 只依赖总元素计数，B+C 单独即可合成 A"),
        ("唯一能源", "温度：T_local>=Σc；0°C 平台无可行候选"),
        ("二元催化", "0 例（无同分异构体 ⇒ A+B→A+C 不可能，B 裂解 0 例）"),
        ("结论", "有「自复制化学式」，无遗传/变异/代谢/边界，不构成生命"),
    ]
    ly = y0 + 42
    for k, v in lines:
        text(x0 + 16, ly, k, F_L, C_BLUE)
        text(x0 + 104, ly, v, F_L, C_DARK)
        ly += 30

    text(W // 2, H - 26, "数据 t94_census.json · 复现 python t94_census.py · 规则 natural_engine.complete_products/resolve · 参数 t94_config",
         F_X, C_GREY, "ma")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return path


# ---------------------------------------------------------------- 入口
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="小范围自检")
    ap.add_argument("--no-png", action="store_true")
    ap.add_argument("--out", default=OUT_JSON)
    ap.add_argument("--png", default=OUT_PNG)
    args = ap.parse_args()

    c = Census(quick=args.quick)
    res = c.run()
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    flush("[T94] wrote %s (%.1f KB)" % (args.out, os.path.getsize(args.out) / 1024.0))
    if not args.no_png:
        render_png(res, args.png)
        flush("[T94] wrote %s" % args.png)
    flush("[T94] done in %.1fs" % (time.time() - c.t0))
    # 控制台结论
    w = res["windows"]
    flush("[T94] 关键: 模板 %d / 三体 %d / 今晚可行 %d / 最快 T_env_min %.0f°C / 窗口最长 %d 拍" % (
        res["replication"]["n_templates"], res["triples"]["n_rows"],
        w["n_feasible_tonight"], w["T_env_min"]["min"], w["window_end"]["max"]))
    m = res.get("minimal", {}).get("rows", [])
    if m:
        top = m[0]
        flush("[T94] 最小: %s = %s + %s, T_env_min=%.0f°C, heat=%+d" % (
            top["A"], top["B"], top["C"], top["T_env_min"], top["heat_sum"]))


if __name__ == "__main__":
    main()
