# -*- coding: utf-8 -*-
"""T78 三轴介质箱实验 —— 独立验证脚本（env-verifier）

只读验证，不修改实验脚本 / 内核 / 三臂结果。本脚本自身产物：
  t78_verify_report.json   验收报告 {"checks":[{name,pass,detail}],"overall":bool}
  t78_verify_det.json      第 1 次 quick 复现跑（--quick --arm main）
  t78_verify_det2.json     第 2 次 quick 复现跑

验收项（对应 task-2）：
  1) 元素守恒：t62_loads.json batchA 按 target_mol=1800 重算投料，与
     summary.initial_composition / conservation / final_composition 逐元素比对；
  2) 可复现：quick 跑两次逐字段一致；与 t78_smoke_main.json 对比（目录 known
     84,225 后 new_substances 应为 5）；
  3) 规则符合：T_REACT 固定 1000 且温度不参与反应判定；门控 p=物态倍率*ρ^1、
     ρ 来自温度轴（热→富集、冷→稀薄）；CAP=20；九种物态对碰撞模式/倍率与
     COLLISION 表一致；介质 (2.0, 1.0, 1.75) = 中·气·温；
  4) 物理合理性：坐标范围/无 NaN、轻/中/重分层、三带与反应直方图求和一致；
  5) 交叉核对：time_series 增量之和 == summary.counts（差 0）。

命令：python t78_verify.py
"""
import copy
import hashlib
import importlib.util
import inspect
import json
import math
import os
import re
import subprocess
import sys
import time
import traceback
from collections import Counter
from datetime import datetime
from types import SimpleNamespace

BASE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(BASE, "t78_three_axis_env.py")
REPORT = os.path.join(BASE, "t78_verify_report.json")
DET = os.path.join(BASE, "t78_verify_det.json")
DET2 = os.path.join(BASE, "t78_verify_det2.json")
SMOKE = os.path.join(BASE, "t78_smoke_main.json")
DOC = os.path.join(BASE, "docs", "MATERIAL_AXES.md")
LOADS = os.path.join(BASE, "t62_loads.json")
ARMS = ("main", "nogate", "nochem")
RESULT_PATH = {a: os.path.join(BASE, "t78_%s_result.json" % a) for a in ARMS}

TARGET_MOL = 1800          # 三臂运行时的投料目标（脚本默认 --target-mol=1800）
FULL_MINUTES = 240
FULL_SNAP = [0, 10, 25, 50, 75, 100, 150, 200, 240]
QUICK_MINUTES = 40
QUICK_TARGET = 400
QUICK_SNAP = [0, 10, 20, 30, 40]
COUNT_KEYS = ("attempts", "complete", "incomplete", "none", "inert", "capped",
              "self_skip", "chem_off")
MODES = ("穿过", "游泳", "黏附", "阻挡")
TIERS = ("轻", "中", "重")
EXPECTED_MODE_MULT = {
    ("气", "气"): ("穿过", 0.18),
    ("气", "液"): ("游泳", 0.45),
    ("液", "气"): ("游泳", 0.45),
    ("液", "液"): ("黏附", 0.60),
    ("气", "固"): ("阻挡", 0.80),
    ("固", "气"): ("阻挡", 0.80),
    ("液", "固"): ("阻挡", 0.90),
    ("固", "液"): ("阻挡", 0.90),
    ("固", "固"): ("阻挡", 1.00),
}
CHECKS = []


# ----------------------------------------------------------------- 工具
def add_check(name, ok, detail):
    CHECKS.append({"name": name, "pass": bool(ok), "detail": detail})
    head = ("PASS " if ok else "FAIL ") + name
    line = detail.replace("\n", " ")
    print("%s :: %s" % (head, line[:480]), flush=True)


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def jload(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def diffs(a, b, path="", limit=8, out=None):
    """递归列出两个 JSON 值的差异（最多 limit 条）。"""
    if out is None:
        out = []
    if len(out) >= limit:
        return out
    if type(a) is not type(b) and not (isinstance(a, (int, float)) and
                                       isinstance(b, (int, float))):
        out.append("%s: 类型 %s vs %s" % (path or "$", type(a).__name__, type(b).__name__))
        return out
    if isinstance(a, dict):
        ka, kb = set(a), set(b)
        if ka != kb:
            out.append("%s: 键差异 多=%s 缺=%s" % (path or "$",
                       sorted(ka - kb)[:5], sorted(kb - ka)[:5]))
        for k in sorted(ka & kb):
            if len(out) >= limit:
                return out
            diffs(a[k], b[k], "%s.%s" % (path, k), limit, out)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append("%s: 长度 %d vs %d" % (path or "$", len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            if len(out) >= limit:
                return out
            diffs(x, y, "%s[%d]" % (path, i), limit, out)
    else:
        if a != b:
            out.append("%s: %r vs %r" % (path or "$", a, b))
    return out


def walk_nonfinite(obj, path, bad, limit=12):
    """找出 NaN/Inf（None 交由调用方按上下文判定）。"""
    if len(bad) >= limit:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk_nonfinite(v, "%s.%s" % (path, k), bad, limit)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_nonfinite(v, "%s[%d]" % (path, i), bad, limit)
    elif isinstance(obj, float):
        if not math.isfinite(obj):
            bad.append("%s=%r" % (path, obj))


def strip_runtime(res):
    r = copy.deepcopy(res)
    r.get("summary", {}).pop("runtime_s", None)
    return r


def load_module():
    sys.path.insert(0, BASE)
    spec = importlib.util.spec_from_file_location("t78env", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # 只执行 import/常量定义，main() 有 __main__ 保护
    return mod


def run_quick(py, out_path, cwd):
    cmd = [py, SCRIPT, "--quick", "--arm", "main", "--out", out_path]
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError("quick 跑失败 rc=%s stderr=%s" % (proc.returncode,
                                                           proc.stderr[-1500:]))
    res = jload(out_path)
    return res, proc.stdout, time.time() - t0


# ----------------------------------------------------------------- 主流程
def _main():
    hashes_before = {p: sha256(p) for p in [SCRIPT, SMOKE] + list(RESULT_PATH.values())
                     if os.path.exists(p)}
    missing = [p for p in [SCRIPT, SMOKE, LOADS, DOC] + list(RESULT_PATH.values())
               if not os.path.exists(p)]
    if missing:
        raise RuntimeError("缺少输入文件: %s" % missing)

    M = load_module()
    import pot_all as P
    from alchemy import attrs as A

    if M.BASE != BASE:
        raise RuntimeError("脚本内 BASE 与本目录不一致: %r vs %r" % (M.BASE, BASE))
    catalog = M.load_catalog_formulas()
    results = {a: jload(RESULT_PATH[a]) for a in ARMS}
    smoke = jload(SMOKE)
    docs = open(DOC, "r", encoding="utf-8").read()
    loads = jload(LOADS)
    rows = loads["batchA"]["rows"]
    rows_total = sum(r["count"] for r in rows)

    def feed_counts(scale):
        c = Counter()
        for r in rows:
            c[r["formula"]] += max(1, int(round(r["count"] * scale)))
        return c

    scale_raw = float(TARGET_MOL) / rows_total
    feed_ic = feed_counts(scale_raw)

    def elem_of(counts):
        el = Counter()
        for f, n in counts.items():
            vec = P.parse_formula(f)
            for i, v in enumerate(vec):
                el[P.ORDER[i]] += n * int(v)
        return el

    def run(name, fn):
        try:
            ok, detail = fn()
        except Exception:
            ok = False
            detail = "EXCEPTION: %s" % traceback.format_exc().strip().splitlines()[-1]
        add_check(name, ok, detail)

    # =================================================== 1) 元素守恒
    def check_conservation():
        problems = []
        texts = []
        # 投料重算
        n_feed = sum(feed_ic.values())
        at_feed = sum(feed_ic[f] * sum(int(v) for v in P.parse_formula(f))
                      for f in feed_ic)
        el_feed = elem_of(feed_ic)
        # 三/二/一价原子总量（v3/v2/v1 与 atoms 自洽）
        v_bad = [r["formula"] for r in rows if r["atoms"] != r["v3"] + r["v2"] + r["v1"]]
        v3 = sum(max(1, int(round(r["count"] * scale_raw))) * r["v3"] for r in rows)
        v2 = sum(max(1, int(round(r["count"] * scale_raw))) * r["v2"] for r in rows)
        v1 = sum(max(1, int(round(r["count"] * scale_raw))) * r["v1"] for r in rows)
        texts.append("投料重算(scale=%.5f): %d 种 / %d 分子 / %d 原子; 9元素各 %d~%d; "
                     "三/二/一价原子 %d/%d/%d (行内 atoms!=v3+v2+v1 的行=%d)"
                     % (scale_raw, len(feed_ic), n_feed, at_feed,
                        min(el_feed.values()), max(el_feed.values()), v3, v2, v1, len(v_bad)))
        if n_feed != 1793:
            problems.append("重算分子数 %d != 1793" % n_feed)
        if at_feed != 18222:
            problems.append("重算原子数 %d != 18222" % at_feed)
        if v_bad:
            problems.append("v3+v2+v1 与 atoms 不自洽的行: %s" % v_bad[:5])
        if abs(v3 - at_feed / 3.0) > 0.01 * at_feed or \
                abs(v2 - at_feed / 3.0) > 0.01 * at_feed or \
                abs(v1 - at_feed / 3.0) > 0.01 * at_feed:
            problems.append("三/二/一价原子不等量: %d/%d/%d" % (v3, v2, v1))
        if len(el_feed) != 9:
            problems.append("元素种数 %d != 9" % len(el_feed))
        if max(el_feed.values()) - min(el_feed.values()) > 0.02 * at_feed:
            problems.append("9 元素不等量: %s" % dict(el_feed))

        for arm in ARMS:
            res = results[arm]
            s = res["summary"]
            ic = s["initial_composition"]
            # 与重算投料完全一致
            d_ic = diffs(ic, dict(feed_ic), "initial_composition")
            if d_ic:
                problems.append("[%s] initial_composition 与重算不一致: %s" % (arm, d_ic))
            if s["initial_N"] != n_feed or s["initial_atoms"] != at_feed:
                problems.append("[%s] initial_N/atoms %d/%d != 重算 %d/%d"
                                % (arm, s["initial_N"], s["initial_atoms"], n_feed, at_feed))
            # conservation 逐元素
            cons = s["conservation"]
            rec_init = {el: el_feed[el] for el in el_feed}
            bad_init = {el: (cons.get(el, {}).get("initial"), rec_init[el])
                        for el in rec_init if cons.get(el, {}).get("initial") != rec_init[el]}
            if bad_init:
                problems.append("[%s] conservation.initial 与重算不一致: %s" % (arm, bad_init))
            if not s["conservation_ok"]:
                problems.append("[%s] conservation_ok=false" % arm)
            bad_final = {el: v for el, v in cons.items() if v["initial"] != v["final"]}
            if bad_final:
                problems.append("[%s] 元素不守恒: %s" % (arm, bad_final))
            # final_composition 逐元素 == conservation.final
            fc = {f: d["count"] for f, d in res["final_composition"].items()}
            el_final = elem_of(fc)
            bad_fc = {el: (el_final.get(el, 0), cons.get(el, {}).get("final"))
                      for el in set(el_final) | set(cons)
                      if el_final.get(el, 0) != cons.get(el, {}).get("final")}
            if bad_fc:
                problems.append("[%s] final_composition 元素和 != conservation.final: %s"
                                % (arm, bad_fc))
            # final_composition 自洽
            if sum(fc.values()) != s["final_N"]:
                problems.append("[%s] composition 计数和 %d != final_N %d"
                                % (arm, sum(fc.values()), s["final_N"]))
            if len(fc) != s["distinct_formulas"]:
                problems.append("[%s] composition 种数 %d != distinct %d"
                                % (arm, len(fc), s["distinct_formulas"]))
            atoms_sum = 0
            atom_bad = []
            for f, d in res["final_composition"].items():
                per = sum(int(x) for x in P.parse_formula(f))
                if d["atoms"] != per:
                    atom_bad.append((f, d["atoms"], per))
                atoms_sum += d["count"] * d["atoms"]
            if atoms_sum != s["final_atoms"]:
                problems.append("[%s] composition 原子和 %d != final_atoms %d"
                                % (arm, atoms_sum, s["final_atoms"]))
            if s["final_atoms"] != s["initial_atoms"]:
                problems.append("[%s] final_atoms %d != initial_atoms %d"
                                % (arm, s["final_atoms"], s["initial_atoms"]))
            if atom_bad:
                problems.append("[%s] composition atoms 与 formula 不符: %s"
                                % (arm, atom_bad[:5]))
            texts.append("[%s] IC=重算 ✓ N=%d/%d 原子=%d; conservation 逐元素=重算且 "
                         "final==initial (9元素); final_comp %d 分子/%d 种, 元素和=final, "
                         "原子和=%d; new_substances=%d distinct=%d"
                         % (arm, s["initial_N"], s["final_N"], s["final_atoms"],
                            s["final_N"], s["distinct_formulas"], atoms_sum,
                            s["new_substances"], s["distinct_formulas"]))
        ok = not problems
        return ok, ("全部通过: " if ok else "问题: %s | " % problems[:6]) + " ; ".join(texts)

    run("1_conservation_elements", check_conservation)

    # =================================================== 2) 可复现（两次 quick）
    quick_texts = {}
    det = det2 = None
    det_stdout = ""

    def check_repro_two():
        nonlocal det, det2, det_stdout
        t0 = time.time()
        det, out1, dt1 = run_quick(sys.executable, DET, BASE)
        det2, out2, dt2 = run_quick(sys.executable, DET2, BASE)
        det_stdout = out1 + "\n" + out2
        s1, s2 = det["summary"], det2["summary"]
        diff = diffs(strip_runtime(det), strip_runtime(det2))
        catalogs_ok = ("catalog formulas: %d" % len(catalog)) in out1 and \
                      ("catalog formulas: %d" % len(catalog)) in out2
        if not catalogs_ok:
            diff.append("quick 运行未打印 catalog formulas: %d" % len(catalog))
        if "saved" not in out1 or "saved" not in out2:
            diff.append("quick 运行未打印 saved")
        for k in ("initial_N", "final_N", "counts", "conservation_ok", "gate", "chem"):
            if s1[k] != s2[k]:
                diff.append("summary.%s 不一致: %r vs %r" % (k, s1[k], s2[k]))
        quick_texts["dt"] = (dt1, dt2)
        quick_texts["summary"] = s1
        detail = ("两次 quick(--quick --arm main, target=400, minutes=40) 全 JSON（除 "
                  "runtime_s）逐字段一致=%s; 耗时 %.2fs/%.2fs; initial_N=%d final_N=%d "
                  "counts=%s new_substances=%d distinct=%d conservation_ok=%s"
                  % (not diff, dt1, dt2, s1["initial_N"], s1["final_N"],
                     json.dumps(s1["counts"], ensure_ascii=False), s1["new_substances"],
                     s1["distinct_formulas"], s1["conservation_ok"]))
        if diff:
            detail += " | 差异: %s" % diff[:6]
        return not diff, detail

    run("2a_reproducibility_two_quick_runs", check_repro_two)

    # =================================================== 2b) 与 smoke_main 对比
    def check_repro_smoke():
        s = det["summary"]
        sm = smoke["summary"]
        diff = []
        fields = ("arm", "seed", "gate", "chem", "initial_N", "initial_atoms",
                  "final_N", "final_atoms", "conservation_ok", "distinct_formulas",
                  "new_substances")
        for k in fields:
            if s.get(k) != sm.get(k):
                diff.append("%s: %r vs smoke %r" % (k, s.get(k), sm.get(k)))
        # counts：除 attempts（new 版把自碰/死粒子采样记 self_skip，不再计入 attempts）外应一致
        counts_diff = []
        for k, v in sm["counts"].items():
            if k == "attempts":
                continue  # 旧版把自碰/死粒子采样计入 attempts；新版记 self_skip，单独核对
            if k not in s["counts"]:
                counts_diff.append("%s 缺失" % k)
            elif s["counts"][k] != v:
                counts_diff.append("%s: %r vs %r" % (k, s["counts"][k], v))
        attempt_identity = s["counts"]["attempts"] + s["counts"].get("self_skip", 0) == \
            sm["counts"]["attempts"]
        ns_det = set(det["new_substances"])
        ns_smoke = set(smoke["new_substances"])
        ns_ok = ns_det == ns_smoke and len(ns_det) == 5
        catalogs_ok = len(catalog) == 84225
        detail = ("smoke_main: initial_N=%d final_N=%d; det: initial_N=%d final_N=%d; "
                  "核心字段一致=%s; new_substances=%d (keys 与 smoke 相同=%s); "
                  "catalog formulas=%d (期望 84225=%s); counts 除 attempts 外一致=%s; "
                  "attempts 口径: det %d + self_skip %d = smoke %d (=%s)"
                  % (sm["initial_N"], sm["final_N"], s["initial_N"], s["final_N"],
                     not [x for x in diff if not x.startswith("counts")], len(ns_det), ns_ok,
                     len(catalog), catalogs_ok, not counts_diff,
                     s["counts"]["attempts"], s["counts"].get("self_skip", 0),
                     sm["counts"]["attempts"], attempt_identity))
        ok = not diff and not counts_diff and attempt_identity and ns_ok and catalogs_ok
        if diff or counts_diff:
            detail += " | 差异: %s %s" % (diff[:4], counts_diff[:4])
        return ok, detail

    run("2b_reproducibility_vs_smoke_main", check_repro_smoke)

    # =================================================== 3a) T_REACT 固定
    def check_treact():
        problems = []
        csrc = inspect.getsource(M.ThreeAxisEnv.contact_step)
        if M.T_REACT != 1000.0:
            problems.append("模块 T_REACT=%r != 1000.0" % M.T_REACT)
        if csrc.count("E.resolve(") != 1:
            problems.append("contact_step 中 E.resolve 调用 %d 次" % csrc.count("E.resolve("))
        if "E.resolve([mi, mj], T_REACT)" not in csrc:
            problems.append("反应判定未使用固定常量 T_REACT")
        if re.search(r"\btemp\b|\.tt\b|\.mt\b", csrc):
            problems.append("contact_step 中引用了温度/质量档字段（温度不应参与反应判定）")
        for arm in ARMS:
            cfg = results[arm]["config"]["collision"]
            if cfg.get("T_REACT") != 1000.0:
                problems.append("[%s] config.collision.T_REACT=%r" % (arm, cfg.get("T_REACT")))
        for phrase in ("不参与", "恒素浓度", "热物质富集恒素", "冷物质稀薄恒素"):
            if phrase not in docs:
                problems.append("docs/MATERIAL_AXES.md 缺少权威表述: %r" % phrase)
        detail = ("T_REACT=1000.0 固定; contact_step 唯一反应调用 E.resolve([mi,mj],T_REACT); "
                  "contact_step 源码不含 temp/.tt; 三臂 config T_REACT=1000.0=%s; "
                  "docs 明文『温度不参与是否反应的判定，只由恒素浓度 ρ_E 决定』=%s"
                  % (all(results[a]["config"]["collision"].get("T_REACT") == 1000.0 for a in ARMS),
                     "不参与" in docs))
        if problems:
            detail = "问题: %s | %s" % (problems, detail)
        return not problems, detail

    run("3a_rule_treact_fixed_1000", check_treact)

    # =================================================== 3b) 门控 p=mult*rho
    def rho_probe():
        env = M.ThreeAxisEnv(minutes=1, seed=1, target_mol=120, gate=True, chem=True,
                             known_formulas=set(), snap_minutes=set())
        cell = env.e_cell(100.0, 100.0)

        def probe(temp):
            env.rho = [0.5] * (M.EX * M.EY)
            env.particles = [SimpleNamespace(x=100.0, y=100.0, temp=temp) for _ in range(9)]
            for _ in range(10):
                env.update_rho()
            return env.rho[cell]

        return probe(3.0), probe(1.75), probe(0.0), cell

    def check_gate():
        problems = []
        csrc = inspect.getsource(M.ThreeAxisEnv.contact_step)
        usrc = inspect.getsource(M.ThreeAxisEnv.update_rho)
        if M.GATE_EXP != 1.0:
            problems.append("GATE_EXP=%r != 1.0" % M.GATE_EXP)
        for needle in ("if self.gate:", "p = mult * (rho ** GATE_EXP)", "p = mult",
                       "rho = self.rho[ei]", "ei = self.e_cell(pi.x, pi.y)"):
            if needle not in csrc:
                problems.append("contact_step 缺少关键行: %r" % needle)
        for needle in ("t = p.temp", "if t > MED_TEMP:", "elif t < MED_TEMP:",
                       "hs[i] += min(1.0, (t - MED_TEMP) / (3.0 - MED_TEMP))",
                       "cs[i] += min(1.0, (MED_TEMP - t) / MED_TEMP)",
                       "star[i] = 0.5 + 0.5 * (hs[i] - cs[i]) / cnt[i]",
                       "v += 0.30 * (star[i] - v)"):
            if needle not in usrc:
                problems.append("update_rho 缺少关键行: %r" % needle)
        hot, neutral, cold, cell = rho_probe()
        if not (hot > 0.60 and abs(neutral - 0.5) < 0.02 and cold < 0.40):
            problems.append("温度→ρ 探针不符: 热=%.4f 温=%.4f 冷=%.4f" % (hot, neutral, cold))
        for arm, want in (("main", True), ("nogate", False), ("nochem", True)):
            cfg_gate = results[arm]["summary"]["gate"]
            if cfg_gate != want:
                problems.append("[%s] summary.gate=%r != %r" % (arm, cfg_gate, want))
            if results[arm]["config"]["collision"].get("GATE_EXP") != 1.0:
                problems.append("[%s] config GATE_EXP != 1.0" % arm)
        detail = ("GATE_EXP=1.0; contact_step: if self.gate: p=mult*(rho**GATE_EXP) else p=mult; "
                  "rho=self.rho[ei], ei=e_cell(pi.x,pi.y); update_rho 由温度场构造: 热(temp=3.0)"
                  "→ρ=%.4f; 温(1.75)→ρ=%.4f; 冷(0.0)→ρ=%.4f (格 %d, 10 步松弛), "
                  "方向=热增/冷减 %s; 三臂 gate 标志 main/nogate/nochem=%s; config GATE_EXP=1.0"
                  % (hot, neutral, cold, cell, "符合" if not problems else "不符",
                     [results[a]["summary"]["gate"] for a in ARMS]))
        if problems:
            detail = "问题: %s | %s" % (problems, detail)
        return not problems, detail

    run("3b_rule_gate_mult_rho_temperature", check_gate)

    # =================================================== 3c) CAP=20
    def check_cap():
        problems = []
        csrc = inspect.getsource(M.ThreeAxisEnv.contact_step)
        if M.CAP != 20:
            problems.append("模块 CAP=%r" % M.CAP)
        if "if na > CAP:" not in csrc or "na = len(mi[\"atoms\"]) + len(mj[\"atoms\"])" not in csrc:
            problems.append("contact_step 未在反应前检查 na>CAP")
        if csrc.index("if na > CAP:") > csrc.index("E.resolve("):
            problems.append("CAP 检查位于 resolve 之后")
        for arm in ARMS:
            res = results[arm]
            s = res["summary"]
            cfg_cap = res["config"]["collision"].get("CAP")
            if cfg_cap != 20:
                problems.append("[%s] config CAP=%r" % (arm, cfg_cap))
            c = s["counts"]
            if c["attempts"] != c["complete"] + c["incomplete"] + c["none"] + c["inert"] + \
                    c["capped"] + c["chem_off"]:
                problems.append("[%s] attempts 分解不闭合: %s" % (arm, c))
            if c["capped"] <= 0:
                problems.append("[%s] capped=0（未观察到 CAP 生效）" % arm)
            big = []
            for ev in res["events"]:
                if ev["type"] in ("complete", "incomplete"):
                    na = sum(sum(int(x) for x in P.parse_formula(f)) for f in ev["in"])
                    if na > 20:
                        big.append((ev["t"], na))
            if big:
                problems.append("[%s] events 中有 na>20 的反应: %s" % (arm, big[:5]))
        detail = ("CAP=20（模块/config）; 反应前先判 na>CAP 再 resolve（序=%s）; "
                  "attempts=complete+incomplete+none+inert+capped+chem_off 三臂均闭合; "
                  "capped 计数 main/nogate/nochem=%s; 抽样 events 的输入原子和均<=20"
                  % ("正确", [results[a]["summary"]["counts"]["capped"] for a in ARMS]))
        if problems:
            detail = "问题: %s | %s" % (problems, detail)
        return not problems, detail

    run("3c_rule_cap_20", check_cap)

    # =================================================== 3d) 碰撞模式/倍率
    def check_mode_mult():
        problems = []
        if M.MODE_MULT != EXPECTED_MODE_MULT:
            problems.append("MODE_MULT 与期望表不一致: %r" % (M.MODE_MULT,))
        if set(M.MODES) != set(MODES):
            problems.append("MODES=%r" % (M.MODES,))
        # 与 attrs.COLLISION 语义一致：固→阻挡(最大倍率)、液→黏附/游泳、气→穿过(最小倍率)
        mults = {}
        for pair, (mode, mult) in M.MODE_MULT.items():
            mults[pair] = mult
            if "固" in pair and mode != "阻挡":
                problems.append("含固物态对 %s 的模式 %s != 阻挡" % (pair, mode))
            if pair == ("气", "气") and mode != "穿过":
                problems.append("气-气模式 != 穿过")
            if pair == ("液", "液") and mode != "黏附":
                problems.append("液-液模式 != 黏附")
            if set(pair) == {"气", "液"} and mode != "游泳":
                problems.append("气-液模式 != 游泳")
        order = [("气", "气"), ("气", "液"), ("液", "液"), ("气", "固"), ("液", "固"), ("固", "固")]
        vals = [mults[p] for p in order]
        if not all(vals[i] < vals[i + 1] for i in range(len(vals) - 1)):
            problems.append("倍率未随阻碍程度单调递增: %s" % list(zip(order, vals)))
        for arm in ARMS:
            cfg = results[arm]["config"]["mode_mult"]
            for pair, (mode, mult) in EXPECTED_MODE_MULT.items():
                key = "%s-%s" % pair
                want = {"mode": mode, "mult": mult}
                if cfg.get(key) != want:
                    problems.append("[%s] config.mode_mult[%s]=%r != %r"
                                    % (arm, key, cfg.get(key), want))
            s = results[arm]["summary"]
            if set(s["mode_counts"]) != set(MODES):
                problems.append("[%s] mode_counts 键=%s" % (arm, sorted(s["mode_counts"])))
            if sum(s["mode_counts"].values()) != s["counts"]["attempts"]:
                problems.append("[%s] mode_counts 和 %d != attempts %d"
                                % (arm, sum(s["mode_counts"].values()),
                                   s["counts"]["attempts"]))
            if set(s["band_reaction"]) != {"bottom", "mid", "top"}:
                problems.append("[%s] band_reaction 键=%s" % (arm, sorted(s["band_reaction"])))
        detail = ("MODE_MULT 9 对与期望表完全一致（气-气 穿过0.18 / 气-液 游泳0.45 / "
                  "液-液 黏附0.60 / 气-固 阻挡0.80 / 液-固 阻挡0.90 / 固-固 阻挡1.00）; "
                  "含固→阻挡、气-气→穿过、液-液→黏附、气-液→游泳，符合 attrs.COLLISION "
                  "语义; 倍率单调 0.18<0.45<0.60<0.80<0.90<1.00; 三臂 config 一致、"
                  "mode_counts 和=attempts; 观测模式计数 main=%s"
                  % json.dumps(results["main"]["summary"]["mode_counts"], ensure_ascii=False))
        if problems:
            detail = "问题: %s | %s" % (problems, detail)
        return not problems, detail

    run("3d_rule_collision_mode_multipliers", check_mode_mult)

    # =================================================== 3e) 介质属性
    def check_medium():
        problems = []
        med = {"mass": 2.0, "state": 1.0, "temperature": 1.75}
        prop = A.property_of(med)
        if prop.get("cell") != "中·气·温":
            problems.append("property_of(2.0,1.0,1.75).cell=%r" % prop.get("cell"))
        beh = prop.get("behavior", {})
        if beh.get("e_field") != "中性":
            problems.append("e_field=%r != 中性" % beh.get("e_field"))
        if beh.get("collision") != A.COLLISION["气"]:
            problems.append("collision 行为与 COLLISION['气'] 不符")
        if beh.get("gravity") != "悬浮/随介质":
            problems.append("gravity 行为=%r" % beh.get("gravity"))
        if (M.MED_MASS, M.MED_STATE, M.MED_TEMP) != (2.0, 1.0, 1.75):
            problems.append("MED_*=%r" % ((M.MED_MASS, M.MED_STATE, M.MED_TEMP),))
        for arm in ARMS:
            w = results[arm]["config"]["world"]
            if w.get("W") != 2000.0 or w.get("H") != 4000.0:
                problems.append("[%s] world W/H=%r" % (arm, (w.get("W"), w.get("H"))))
            if w.get("medium") != med:
                problems.append("[%s] world.medium=%r" % (arm, w.get("medium")))
        if A.THRESHOLDS != {"mass": (1.67, 2.30), "state": (1.70, 2.22),
                            "temperature": (1.50, 2.00)}:
            problems.append("attrs.THRESHOLDS=%r" % (A.THRESHOLDS,))
        detail = ("attrs.property_of({mass:2.0,state:1.0,temperature:1.75}) = %r; "
                  "grades=%r; behavior.e_field=%r, collision=%r, gravity=%r; "
                  "MED_*=(2.0,1.0,1.75); 三臂 config.world.medium 一致; "
                  "attrs.THRESHOLDS 与 docs 一致（1.67/2.30, 1.70/2.22, 1.50/2.00）"
                  % (prop.get("cell"), prop.get("grades"), beh.get("e_field"),
                     beh.get("collision"), beh.get("gravity")))
        if problems:
            detail = "问题: %s | %s" % (problems, detail)
        return not problems, detail

    run("3e_rule_medium_property", check_medium)

    # =================================================== 4a) 坐标范围 / 有限性
    def raw_replication():
        W, H = M.W, M.H
        M.E.set_fast(True)
        env = M.ThreeAxisEnv(minutes=QUICK_MINUTES, seed=20261119, target_mol=QUICK_TARGET,
                             gate=True, chem=True, known_formulas=catalog,
                             snap_minutes=set(QUICK_SNAP))
        env.arm = "verify_raw"
        env._last_counts = Counter()
        env._last_modes = Counter()
        raw_snaps = {}
        st = {"steps": 0, "x<0": 0, "x>W": 0, "y<0": 0, "y>H": 0, "nonfinite": 0,
              "x>=W": 0, "y>=H": 0, "maxx": -1.0, "maxy": -1.0,
              "snap_x>=W": 0, "snap_y>=H": 0}

        def scan():
            st["steps"] += 1
            for p in env.particles:
                x, y = p.x, p.y
                if not (math.isfinite(x) and math.isfinite(y) and
                        math.isfinite(p.vx) and math.isfinite(p.vy)):
                    st["nonfinite"] += 1
                    continue
                if x < 0:
                    st["x<0"] += 1
                if x > W:
                    st["x>W"] += 1
                if y < 0:
                    st["y<0"] += 1
                if y > H:
                    st["y>H"] += 1
                if x >= W:
                    st["x>=W"] += 1
                if y >= H:
                    st["y>=H"] += 1
                st["maxx"] = max(st["maxx"], x)
                st["maxy"] = max(st["maxy"], y)

        for t in range(QUICK_MINUTES):
            if t in env.snap_minutes:
                env._snapshot(t)
                raw_snaps[t] = ([(p.x, p.y, p.mol["formula"]) for p in env.particles],
                                list(env.rho))
            env.move()
            scan()
            env.update_rho()
            before = Counter(env.counts)
            bm = Counter(env.mode_counts)
            env.contact_step(t)
            scan()
            for k in COUNT_KEYS:
                env._last_counts[k] = env.counts[k] - before[k]
            env._last_modes = {m: env.mode_counts[m] - bm.get(m, 0) for m in M.MODES}
            env.time_series.append(env._row(t))
        if env.minutes in env.snap_minutes:
            env._snapshot(env.minutes - 1)
            raw_snaps[env.minutes - 1] = ([(p.x, p.y, p.mol["formula"])
                                           for p in env.particles], list(env.rho))
        expected = []
        for t in sorted(raw_snaps):
            pts, rho = raw_snaps[t]
            exp_pts = []
            for x, y, f in pts:
                exp_pts.append([round(x, 1), round(y, 1), f])
                if x >= W:
                    st["snap_x>=W"] += 1
                if y >= H:
                    st["snap_y>=H"] += 1
            expected.append({"t": t, "n": len(exp_pts), "points": exp_pts,
                             "rho": [round(v, 3) for v in rho]})
        return st, expected

    def check_bounds():
        problems = []
        texts = []
        # 三臂已存快照：闭区间内、无越界、有限
        for arm in ARMS:
            res = results[arm]
            snaps = res["snapshots"]
            labels = [s["t"] for s in snaps]
            want_labels = [x for x in FULL_SNAP if x < FULL_MINUTES] + [FULL_MINUTES - 1]
            n_out = 0
            n_eq_w = n_eq_h = 0
            npt = 0
            for s in snaps:
                npt += len(s["points"])
                if s["n"] != len(s["points"]):
                    problems.append("[%s] snapshot t=%s n=%d != len(points)=%d"
                                    % (arm, s["t"], s["n"], len(s["points"])))
                for x, y, f in s["points"]:
                    if not (math.isfinite(x) and math.isfinite(y)):
                        problems.append("[%s] snapshot 坐标非有限: %r,%r" % (arm, x, y))
                        continue
                    if x < 0 or x > 2000.0 or y < 0 or y > 4000.0:
                        n_out += 1
                    if x == 2000.0:
                        n_eq_w += 1
                    if y == 4000.0:
                        n_eq_h += 1
                if len(s["rho"]) != M.EX * M.EY:
                    problems.append("[%s] snapshot rho 长度 %d" % (arm, len(s["rho"])))
                if any((not math.isfinite(v)) or v < 0.0 or v > 1.0 for v in s["rho"]):
                    problems.append("[%s] snapshot rho 越界/非有限" % arm)
            if n_out:
                problems.append("[%s] %d 个快照点越出闭区间 [0,2000]x[0,4000]" % (arm, n_out))
            if labels != want_labels:
                problems.append("[%s] 快照标签 %r != 由源码推导 %r（末帧为 minutes-1 的标注）"
                                % (arm, labels, want_labels))
            if snaps[-1]["n"] != res["summary"]["final_N"]:
                problems.append("[%s] 末快照 n=%d != final_N=%d"
                                % (arm, snaps[-1]["n"], res["summary"]["final_N"]))
            texts.append("[%s] %d 帧/%d 点: 越界=%d, 记录值恰为x=2000.0 的 %d 点 / "
                         "y=4000.0 的 %d 点（round(·,1) 舍入）, 末帧 n=%d=final_N"
                         % (arm, len(snaps), npt, n_out, n_eq_w, n_eq_h, snaps[-1]["n"]))
        # 原始坐标进程内复核（与 det 同 seed/参数：quick main）
        st, expected = raw_replication()
        rep_diff = diffs(expected, det["snapshots"], "snapshots", limit=5) if det else \
            ["det 未生成"]
        raw_problems = []
        if st["x<0"] or st["x>W"] or st["y<0"] or st["y>H"] or st["nonfinite"]:
            raw_problems.append("原始坐标出现越界/非有限: %s" % {k: st[k] for k in
                                ("x<0", "x>W", "y<0", "y>H", "nonfinite")})
        if st["snap_x>=W"] or st["snap_y>=H"]:
            raw_problems.append("快照时刻原始坐标 >= W/H: %s" % {k: st[k] for k in
                                ("snap_x>=W", "snap_y>=H")})
        # 逐 step 检查的原始坐标允许等于 W/H（反射后闭区间），但不应出现；出现则记录
        if st["x>=W"] or st["y>=H"]:
            raw_problems.append("原始坐标恰等于边界 W/H 的样本: x>=W %d, y>=H %d（应为 0）"
                                % (st["x>=W"], st["y>=H"]))
        if rep_diff:
            raw_problems.append("进程内复现快照与 det 不完全一致: %s" % rep_diff[:3])
        texts.append("原始坐标复核(quick main 进程内逐 step): %d 步扫描, max x=%.4f (<2000=%s), "
                     "max y=%.4f (<4000=%s), 非有限=0; 原始坐标 0<=x<=2000/0<=y<=4000 全程成立; "
                     "与 det 快照逐点一致=%s"
                     % (st["steps"], st["maxx"], st["maxx"] < M.W, st["maxy"],
                        st["maxy"] < M.H, not rep_diff))
        problems.extend(raw_problems)
        detail = (" | ".join(texts) + (" | 问题: %s" % problems[:6] if problems else
                  " → 快照中 x=2000.0/y=4000.0 系 round(·,1) 舍入，原始坐标严格处于 [0,2000)/[0,4000)"))
        return not problems, detail

    run("4a_physics_positions_bounds_finite", check_bounds)

    # =================================================== 4b) 轻/中/重分层
    def check_layering():
        problems = []
        texts = []
        for arm in ARMS:
            res = results[arm]
            s = res["summary"]
            late = [r for r in res["time_series"] if r["t"] >= 120]
            bad = []
            for r in late:
                y = r["y_mean"]
                if None in y.values():
                    bad.append((r["t"], "None"))
                elif not (y["轻"] > y["中"] > y["重"]):
                    bad.append((r["t"], y))
            if bad:
                problems.append("[%s] t>=120 有 %d 行不满足 轻>中>重: %s" % (arm, len(bad), bad[:3]))
            last = res["time_series"][-1]["y_mean"]
            if last["轻"] <= last["中"] or last["中"] <= last["重"]:
                problems.append("[%s] 末行 y_mean 非 轻>中>重: %r" % (arm, last))
            texts.append("[%s] t=%d 末行 y_mean 轻/中/重=%.1f/%.1f/%.1f（轻-中=%.1f, 中-重=%.1f）; "
                         "t>=120 的 %d 行全部严格 轻>中>重"
                         % (arm, res["time_series"][-1]["t"], last["轻"], last["中"], last["重"],
                            last["轻"] - last["中"], last["中"] - last["重"], len(late)))
        detail = " | ".join(texts)
        if problems:
            detail += " | 问题: %s" % problems[:5]
        return not problems, detail

    run("4b_physics_layering_y_mean", check_layering)

    # =================================================== 4c) 三带/直方图/组成求和
    def check_sums():
        problems = []
        texts = []
        for arm in ARMS:
            res = results[arm]
            s = res["summary"]
            c = s["counts"]
            ci = c["complete"] + c["incomplete"]
            # 逐行不变量
            row_bad = []
            for r in res["time_series"]:
                if sum(r["band"].values()) != r["N"]:
                    row_bad.append((r["t"], "band", sum(r["band"].values()), r["N"]))
                for key in ("mass", "state", "temp"):
                    if sum(r[key].values()) != r["N"]:
                        row_bad.append((r["t"], key, sum(r[key].values()), r["N"]))
                if r["atoms"] != s["initial_atoms"]:
                    row_bad.append((r["t"], "atoms", r["atoms"], s["initial_atoms"]))
                if sum(r["mode"].values()) != r["attempts"]:
                    row_bad.append((r["t"], "mode", sum(r["mode"].values()), r["attempts"]))
                if r["N"] <= 0:
                    row_bad.append((r["t"], "N<=0", r["N"], 0))
            if row_bad:
                problems.append("[%s] 行不变量不成立 %d 处: %s" % (arm, len(row_bad), row_bad[:4]))
            # 反应带 / 直方图
            if sum(s["band_reaction"].values()) != ci:
                problems.append("[%s] band_reaction 和 %d != complete+incomplete %d"
                                % (arm, sum(s["band_reaction"].values()), ci))
            if sum(res["reaction_y_hist"]) != ci:
                problems.append("[%s] reaction_y_hist 和 %d != ci %d"
                                % (arm, sum(res["reaction_y_hist"]), ci))
            # 终态三带 / 竖直直方图
            if sum(b["n"] for b in res["bands"].values()) != s["final_N"]:
                problems.append("[%s] bands.n 和 %d != final_N %d"
                                % (arm, sum(b["n"] for b in res["bands"].values()), s["final_N"]))
            if sum(res["vertical_hist"]["all"]) != s["final_N"]:
                problems.append("[%s] vertical_hist.all 和 %d != final_N %d"
                                % (arm, sum(res["vertical_hist"]["all"]), s["final_N"]))
            last_mass = res["time_series"][-1]["mass"]
            for tier in TIERS:
                if sum(res["vertical_hist"][tier]) != last_mass[tier]:
                    problems.append("[%s] vertical_hist[%s] 和 != 末行 mass[%s]"
                                    % (arm, tier, tier))
            if sum(b["atoms"] for b in res["bands"].values()) != s["final_atoms"]:
                problems.append("[%s] bands.atoms 和 != final_atoms" % arm)
            # 反应地理
            if sum(g["attempts"] for g in res["reaction_geography"]) != c["attempts"]:
                problems.append("[%s] reaction_geography.attempts 和 != attempts" % arm)
            if sum(g["reactions"] for g in res["reaction_geography"]) != ci:
                problems.append("[%s] reaction_geography.reactions 和 != ci" % arm)
            if len(res["reaction_geography"]) != 11:
                problems.append("[%s] reaction_geography 桶数 %d != 11"
                                % (arm, len(res["reaction_geography"])))
            ci_obs = res["reaction_y_hist"]
            texts.append("[%s] 240 行三带/质量/物态/温度/模式求和全=N、atoms=%d 恒定; "
                         "band_reaction 和=%d=ci; reaction_y_hist 和=%d; bands.n 和=%d=final_N; "
                         "vertical_hist 和=%d; geo attempts/reactions=%d/%d"
                         % (arm, s["initial_atoms"], sum(s["band_reaction"].values()),
                            sum(ci_obs), sum(b["n"] for b in res["bands"].values()),
                            sum(res["vertical_hist"]["all"]),
                            sum(g["attempts"] for g in res["reaction_geography"]),
                            sum(g["reactions"] for g in res["reaction_geography"])))
        detail = " | ".join(texts)
        if problems:
            detail = "问题: %s | %s" % (problems[:6], detail)
        return not problems, detail

    run("4c_physics_histogram_band_composition_sums", check_sums)

    # =================================================== 4d) 无 NaN/None
    def check_nan():
        bad = []
        for arm in ARMS:
            res = results[arm]
            walk_nonfinite(res["time_series"], "[%s].time_series" % arm, bad, 20)
            walk_nonfinite(res["summary"], "[%s].summary" % arm, bad, 20)
            walk_nonfinite(res["vertical_hist"], "[%s].vertical_hist" % arm, bad, 20)
            walk_nonfinite(res["reaction_y_hist"], "[%s].reaction_y_hist" % arm, bad, 20)
            walk_nonfinite(res["snapshots"], "[%s].snapshots" % arm, bad, 20)
            walk_nonfinite(res["reaction_geography"], "[%s].geo" % arm, bad, 20)
            walk_nonfinite(res["bands"], "[%s].bands" % arm, bad, 20)
            # y_mean 的 None 仅允许在对应档计数为 0 时，且范围合法
            for r in res["time_series"]:
                for tier in TIERS:
                    y = r["y_mean"][tier]
                    n = r["mass"][tier]
                    if y is None:
                        if n != 0:
                            bad.append("[%s] t=%d mass[%s]=%d 但 y_mean=None"
                                       % (arm, r["t"], tier, n))
                    elif not (0.0 <= y <= 4000.0):
                        bad.append("[%s] t=%d y_mean[%s]=%r 越界" % (arm, r["t"], tier, y))
                if not (0.0 <= r["rho_mean"] <= 1.0) or not (0.0 <= r["rho_p10"] <= 1.0) \
                        or not (0.0 <= r["rho_p90"] <= 1.0) or r["rho_p10"] > r["rho_p90"]:
                    bad.append("[%s] t=%d rho 统计异常" % (arm, r["t"]))
                if not (0.0 <= r["mass_mean"] <= 3.0 and 0.0 <= r["state_mean"] <= 3.0
                        and 0.0 <= r["temp_mean"] <= 3.0):
                    bad.append("[%s] t=%d 三轴均值越界" % (arm, r["t"]))
                if r["distinct"] < 1:
                    bad.append("[%s] t=%d distinct<1" % (arm, r["t"]))
            # 快照坐标有限 + rho 有限
            for s in res["snapshots"]:
                for x, y, f in s["points"]:
                    if not (math.isfinite(x) and math.isfinite(y)):
                        bad.append("[%s] t=%s 坐标非有限" % (arm, s["t"]))
                        break
        detail = ("time_series/summary/快照/直方图/几何 递归扫描 NaN/Inf: %d 处; "
                  "y_mean None 仅当该档计数为 0（三臂均无该情况）; rho/三轴均值/坐标全部在合法区间"
                  % len(bad))
        if bad:
            detail = "问题: %s | %s" % (bad[:8], detail)
        return not bad, detail

    run("4d_physics_no_nan", check_nan)

    # =================================================== 5) 交叉核对增量
    def check_cross():
        problems = []
        texts = []
        for arm in ARMS:
            res = results[arm]
            s = res["summary"]
            ts = res["time_series"]
            inc = {k: sum(r[k] for r in ts) for k in COUNT_KEYS}
            d = {k: inc[k] - s["counts"][k] for k in COUNT_KEYS if inc[k] != s["counts"][k]}
            if d:
                problems.append("[%s] time_series 增量之和 - summary.counts = %s" % (arm, d))
            mode_inc = {m: sum(r["mode"][m] for r in ts) for m in MODES}
            dm = {m: mode_inc[m] - s["mode_counts"][m] for m in MODES
                  if mode_inc[m] != s["mode_counts"][m]}
            if dm:
                problems.append("[%s] time_series.mode 之和 - summary.mode_counts = %s"
                                % (arm, dm))
            c = s["counts"]
            if c["attempts"] != c["complete"] + c["incomplete"] + c["none"] + c["inert"] + \
                    c["capped"] + c["chem_off"]:
                problems.append("[%s] summary attempts 分解不闭合" % arm)
            n_rows = len(ts)
            if n_rows != FULL_MINUTES:
                problems.append("[%s] time_series 行数 %d != %d" % (arm, n_rows, FULL_MINUTES))
            if [r["t"] for r in ts] != list(range(FULL_MINUTES)):
                problems.append("[%s] time_series t 序列不连续" % arm)
            if sum(r["complete"] + r["incomplete"] for r in ts) != \
                    sum(s["band_reaction"].values()):
                problems.append("[%s] 逐行 complete+incomplete 和 != band_reaction 和" % arm)
            texts.append("[%s] 8 个计数键逐行增量之和 == summary.counts（差 0，%s）; "
                         "4 个模式增量之和 == mode_counts; attempts 分解闭合"
                         % (arm, ",".join("%s:%d" % (k, s["counts"][k]) for k in COUNT_KEYS)))
        detail = " | ".join(texts)
        if problems:
            detail = "问题: %s | %s" % (problems[:6], detail)
        return not problems, detail

    run("5_crosscheck_series_vs_summary", check_cross)

    # =================================================== 6) 组成/新物种结构
    def check_composition_struct():
        problems = []
        texts = []
        for arm in ARMS:
            res = results[arm]
            s = res["summary"]
            ic = s["initial_composition"]
            if sum(ic.values()) != s["initial_N"]:
                problems.append("[%s] initial_composition 和 %d != initial_N"
                                % (arm, sum(ic.values())))
            ns = res["new_substances"]
            if len(ns) != s["new_substances"]:
                problems.append("[%s] new_substances 数 %d != summary %d"
                                % (arm, len(ns), s["new_substances"]))
            in_catalog = [f for f in ns if f in catalog]
            if in_catalog:
                problems.append("[%s] new_substances 中有公式已在 84,225 目录（不应记为 new）: %s"
                                % (arm, in_catalog[:5]))
            struct_bad = []
            for f, d in ns.items():
                atom_counter = Counter(d["atoms"])
                vec = P.parse_formula(f)
                want = Counter()
                for i, v in enumerate(vec):
                    want[P.ORDER[i]] += int(v)
                if atom_counter != want:
                    struct_bad.append((f, "atoms 与 formula 不符"))
                if len(d["edges"]) < 1 or any(len(e) != 3 for e in d["edges"]):
                    struct_bad.append((f, "edges 结构异常"))
                ok_idx = all(isinstance(e[0], int) and isinstance(e[1], int)
                             and 0 <= e[0] < len(d["atoms"]) and 0 <= e[1] < len(d["atoms"])
                             for e in d["edges"])
                if not ok_idx:
                    struct_bad.append((f, "edges 下标越界"))
                if not (0 <= d["first_t"] < FULL_MINUTES):
                    struct_bad.append((f, "first_t=%r 越界" % (d["first_t"],)))
            if struct_bad:
                problems.append("[%s] new_substances 结构问题: %s" % (arm, struct_bad[:5]))
            if arm == "nochem":
                if ns:
                    problems.append("[nochem] chem=False 却出现 new_substances=%d" % len(ns))
                if s["distinct_formulas"] != len(ic):
                    problems.append("[nochem] distinct %d != 投料种数 %d"
                                    % (s["distinct_formulas"], len(ic)))
            texts.append("[%s] initial_composition 和=%d=initial_N; new_substances=%d 且均不在 "
                         "目录中、atoms/edges/first_t 结构合法%s"
                         % (arm, sum(ic.values()), len(ns), "（nochem 应为 0）"
                            if arm == "nochem" else ""))
        detail = " | ".join(texts)
        if problems:
            detail = "问题: %s | %s" % (problems[:6], detail)
        return not problems, detail

    run("6_structure_composition_new_substances", check_composition_struct)

    # =================================================== 7) 三臂行为自洽
    def check_arms():
        problems = []
        ic0 = results["main"]["summary"]["initial_composition"]
        cons0 = results["main"]["summary"]["conservation"]
        for arm in ARMS:
            s = results[arm]["summary"]
            if s["initial_composition"] != ic0:
                problems.append("[%s] initial_composition 与 main 不同" % arm)
            if {k: v["initial"] for k, v in s["conservation"].items()} != \
                    {k: v["initial"] for k, v in cons0.items()}:
                problems.append("[%s] conservation.initial 与 main 不同" % arm)
            if s["initial_N"] != 1793 or s["initial_atoms"] != 18222:
                problems.append("[%s] initial_N/atoms=%d/%d"
                                % (arm, s["initial_N"], s["initial_atoms"]))
            if not s["conservation_ok"]:
                problems.append("[%s] 不守恒" % arm)
        m = results["main"]["summary"]
        n = results["nogate"]["summary"]
        nc = results["nochem"]["summary"]
        if not (m["gate"] is True and m["chem"] is True):
            problems.append("main gate/chem 标志错")
        if not (n["gate"] is False and n["chem"] is True):
            problems.append("nogate gate/chem 标志错")
        if not (nc["gate"] is True and nc["chem"] is False):
            problems.append("nochem gate/chem 标志错")
        if nc["counts"]["complete"] != 0 or nc["counts"]["incomplete"] != 0 or \
                nc["counts"]["none"] != 0:
            problems.append("nochem 化学关闭但 complete/incomplete/none 非 0")
        if nc["counts"]["chem_off"] <= 0:
            problems.append("nochem chem_off=0（化学关闭分支未触发）")
        if nc["final_N"] != nc["initial_N"]:
            problems.append("nochem 分子数变化 %d->%d" % (nc["initial_N"], nc["final_N"]))
        if m["counts"]["complete"] <= 0 or n["counts"]["complete"] <= 0:
            problems.append("main/nogate 无 complete 反应")
        rate_main = m["counts"]["inert"] / max(1, m["counts"]["attempts"])
        rate_nogate = n["counts"]["inert"] / max(1, n["counts"]["attempts"])
        if not rate_main > rate_nogate:
            problems.append("main 惰性率 %.3f 未高于 nogate %.3f（门控抑制未体现）"
                            % (rate_main, rate_nogate))
        detail = ("三臂投料完全相同（IC/守恒初值/1793 分子/18222 原子）; "
                  "main: gate=on chem=on complete=%d final_N=%d; "
                  "nogate: gate=off chem=on complete=%d final_N=%d; "
                  "nochem: gate=on chem=off complete=0 chem_off=%d final_N=%d=initial; "
                  "惰性率 main=%.2f%% > nogate=%.2f%%（门控 p=mult·ρ 使更多采样判惰性，"
                  "与设计一致）"
                  % (m["counts"]["complete"], m["final_N"], n["counts"]["complete"],
                     n["final_N"], nc["counts"]["chem_off"], nc["final_N"],
                     rate_main * 100, rate_nogate * 100))
        if problems:
            detail = "问题: %s | %s" % (problems[:6], detail)
        return not problems, detail

    run("7_arm_behavior_sanity", check_arms)

    # =================================================== 8) 输入未变
    def check_immutable():
        after = {p: sha256(p) for p in hashes_before}
        changed = {p: (hashes_before[p][:16], after[p][:16]) for p in hashes_before
                   if hashes_before[p] != after[p]}
        texts = "; ".join("%s=%s" % (os.path.basename(p), h[:16]) for p, h in sorted(after.items()))
        allowed = {DET, DET2}
        others = {p: v for p, v in changed.items() if p not in allowed}
        detail = ("脚本/三臂结果/smoke 的 SHA256(前16) 验证前后不变%s: %s"
                  % ("（含 det 允许变化）" if len(changed) > len(others) else "",
                     texts))
        if others:
            detail = "输入在验证期间被修改: %s | %s" % (others, detail)
        return not others, detail

    run("8_input_files_immutable", check_immutable)

    return {
        "checks": CHECKS,
        "overall": all(c["pass"] for c in CHECKS),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_mol": TARGET_MOL,
        "script": SCRIPT,
        "script_sha256": hashes_before.get(SCRIPT),
        "results_sha256": {os.path.basename(p): hashes_before.get(p)
                           for p in RESULT_PATH.values()},
        "python": sys.version.split()[0],
    }


def write_report(report):
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print("\n报告已写入 %s" % REPORT)
    print("overall = %s (%d/%d checks pass)"
          % (report["overall"], sum(1 for c in report["checks"] if c["pass"]),
             len(report["checks"])))


def main():
    t0 = time.time()
    try:
        report = _main()
    except Exception:
        add_check("harness", False, "验证脚本内部异常:\n" + traceback.format_exc()[-2500:])
        report = {"checks": CHECKS, "overall": False,
                  "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                  "python": sys.version.split()[0]}
    report["elapsed_s"] = round(time.time() - t0, 1)
    write_report(report)
    return 0 if report["overall"] else 1


if __name__ == "__main__":
    sys.exit(main())
