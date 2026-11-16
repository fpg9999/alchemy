# -*- coding: utf-8 -*-
"""t56_ratio_6elem.py —— T56：调整价数比例 + 加入三种散素的 2D 粒子环境实验

在 T55 的基础上按用户新要求修改投料：

1. **价数比例**：三价元素原子数 < 二价元素原子数 < 一价元素原子数。
   投料（双原子单质，键级=价数）：
     三价：O2（秩，3 价）800 + K2（沌，3 价）800 = 1600 分子 / 3200 原子
     二价：X2（晶，2 价）1400 + A2（气，2 价）1400 = 2800 分子 / 5600 原子
     一价：C2（冰，1 价）2400 + F2（焰，1 价）2400 = 4800 分子 / 9600 原子
   合计 9200 个双原子单质 / 18400 个原子；3200 : 5600 : 9600 = 1 : 1.75 : 3。
2. **加入三种散素**：K（沌，3 价）、A（气，2 价）、F（焰，1 价）——
   即投料中新增 K2 / A2 / F2 三种散素单质（其余仍为聚素 O/X/C）。
3. **允许更大分子量**：不设分子尺寸上限；T55 的产物最大 9 原子，本次跨大类
   （聚素-散素，周期表距离 d=6 优先成键）与不完全反应会让分子长到 20~30+ 原子。
4. 环境、温度（1000→0°C，1000 分钟）、初速度设计（前 500 分钟每单质 ≥500 次
   角-对角穿越）、每次碰撞衰减 0.2% 等与 T55 完全一致（复用 t55_kinetic_env）。

输出：
  t56_kinetic_result.json     主实验
  t56_control_no_chem.json    无化学对照（500 分钟，穿越验证）

用法：
  python t56_ratio_6elem.py              # 主实验 + 对照
  python t56_ratio_6elem.py --control    # 只跑对照
"""
import argparse
import json
import sys
import time

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import pot_all as P
from t55_kinetic_env import KineticEnvironment, run_control

LOAD_SPEC = [
    # (批次, 说明, 分子式, 数量)
    ("A", "三价单质（价3）", "O2", 800),   # 秩 O
    ("A", "三价单质（价3）", "K2", 800),   # 沌 K（散素）
    ("B", "二价单质（价2）", "X2", 1400),  # 晶 X
    ("B", "二价单质（价2）", "A2", 1400),  # 气 A（散素）
    ("C", "一价单质（价1）", "C2", 2400),  # 冰 C
    ("C", "一价单质（价1）", "F2", 2400),  # 焰 F（散素）
]

SNAP_MINUTES = [0, 2, 5, 10, 25, 50, 100, 200, 300, 400,
                500, 600, 700, 800, 900, 950, 980, 995, 1000]
SEED = 20261117


def load_catalog_formulas():
    """84,225 条大锅目录的分子式集合（用于判定'目录外新物质'）。"""
    idx = json.load(open(BASE + r"\t4_catalog_index.json", encoding="utf-8"))
    return {r["formula"] for r in idx}


def ratio_info():
    """按价数统计投料比例（分子数 / 原子数）。"""
    mols = {3: 0, 2: 0, 1: 0}
    atoms = {3: 0, 2: 0, 1: 0}
    elements = {3: [], 2: [], 1: []}
    for _tag, _desc, f, count in LOAD_SPEC:
        e = f[0]
        v = P.VAL[e]
        mols[v] += count
        atoms[v] += 2 * count
        elements[v].append(e)
    ok = atoms[3] < atoms[2] < atoms[1]
    return {
        "valence3": {"elements": elements[3], "molecules": mols[3], "atoms": atoms[3]},
        "valence2": {"elements": elements[2], "molecules": mols[2], "atoms": atoms[2]},
        "valence1": {"elements": elements[1], "molecules": mols[1], "atoms": atoms[1]},
        "atoms_ratio": [atoms[3], atoms[2], atoms[1]],
        "strict_increasing": bool(ok),
        "total_molecules": sum(mols.values()),
        "total_atoms": sum(atoms.values()),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--control", action="store_true")
    args = ap.parse_args(argv)
    if args.control:
        res = run_control(minutes=500, seed=args.seed, load_spec=LOAD_SPEC)
        json.dump(res, open(BASE + r"\t56_control_no_chem.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("saved t56_control_no_chem.json")
        print(json.dumps(res["stats"], ensure_ascii=False, indent=1))
        return
    ri = ratio_info()
    print("投料比例:", json.dumps(ri, ensure_ascii=False))
    known = load_catalog_formulas()
    t_start = time.time()
    env = KineticEnvironment(minutes=args.minutes, seed=args.seed,
                             load_spec=LOAD_SPEC, known_formulas=known,
                             event_limit=30000, snap_minutes=SNAP_MINUTES,
                             color_mode="bitmask")
    res = env.run()
    res["ratio"] = ri
    res["catalog_size"] = len(known)
    res["config"]["experiment"] = "T56 价数比例 3<2<1 + 三种散素 K/A/F"
    res["summary"]["runtime_s"] = round(time.time() - t_start, 1)
    json.dump(res, open(BASE + r"\t56_kinetic_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t56_kinetic_result.json", "runtime", res["summary"]["runtime_s"], "s")
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1)[:2500])


if __name__ == "__main__":
    main()
