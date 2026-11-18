# -*- coding: utf-8 -*-
"""内核演示：四个入口 + 骨架分类表（可直接改造成"物质卡"生成器）。

运行（在仓库根目录）：
    python examples/demo_kernel.py
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import alchemy  # noqa: E402


def demo_simulate():
    print("=" * 70)
    print("1) 大锅反应 simulate()")
    print("=" * 70)
    for feed in (["O", "K"], ["O", "X", "C"], ["O", "O", "W", "A", "F"]):
        mols = alchemy.simulate(feed)
        if mols is None:
            print(f"  {''.join(feed):12} -> None（价数接不满）")
            continue
        desc = " + ".join(alchemy.formula_of(m["atoms"]) for m in mols)
        print(f"  {''.join(feed):12} -> {desc}")
    print(f"  {'OXCF':12} -> {alchemy.simulate(['O','X','C','F'])}（总价数 7，奇数）")


def demo_geometry():
    print("\n" + "=" * 70)
    print("2) 六边形摆放 embed() / validate()")
    print("=" * 70)
    m = alchemy.simulate(["O", "X", "C"])[0]
    place = alchemy.embed(m["atoms"], m["edges"])
    ok, msg = alchemy.validate(place, m["atoms"], m["edges"])
    print(f"  OXC 原子 = {m['atoms']}, 键 = {m['edges']}")
    print(f"  摆放   = {place}")
    print(f"  校验   = {ok} ({msg})")
    # 故意给一个非法摆放
    bad = {0: (0, 0), 1: (5, 5), 2: (0, 1)}
    print(f"  非法摆放 -> {alchemy.validate(bad, m['atoms'], m['edges'])}")


def demo_catalog():
    print("\n" + "=" * 70)
    print("3) 物质目录 catalog")
    print("=" * 70)
    cat = alchemy.get_catalog()
    st = cat.stats()
    print(f"  总条数 = {st['total']:,}   ≤16 原子 = {st['le16']:,}   "
          f"最大原子数 = {st['max_natoms']}   缺 place = {st['missing_place']}")
    for f in ("OXC", "OK", "LF", "OXCPWKA"):
        rec = cat[f]
        print(f"  {f:10} {rec['zh']:10} natoms={rec['natoms']}  feed={tuple(rec['feed'])}")


def demo_classify():
    print("\n" + "=" * 70)
    print("4) 骨架分类 classify()")
    print("=" * 70)
    m = alchemy.simulate(["O", "X", "C"])[0]
    out = alchemy.classify(m["atoms"], m["edges"])
    print(f"  OXC: 类目={out['category']}  在库={out['in_library']}  稳定={out['stable']}")
    print(f"       6 级块 = {[(b['formula'], b['kind']) for b in out['level6']['blocks']]}")
    print(f"       三层   = 骨架{out['layers']['skeleton']} "
          f"连接{out['layers']['bridge']} 终端{out['layers']['cap']}")

    # 骨架卡的雏形：一条物质 -> 一张分类表
    print("\n  " + "-" * 66)
    print(f"  {'分子式':10} {'中文':10} {'原子':>4} {'类目':16} {'6级骨架块':22} {'库':>3} {'稳定':>4}")
    print("  " + "-" * 66)
    for f in ("OK", "O2X2C2F2", "XCF", "OAF", "OXCPWKA", "O2X3C3K3A3", "CF", "LF"):
        rec = alchemy.get_catalog().get(f)
        if rec is None:
            continue
        c = alchemy.classify_record(rec)
        blocks = " ".join(b["formula"] for b in c["level6"]["blocks"]) or "-"
        print(f"  {f:10} {c['zh']:10} {c['natoms']:>4} {c['category']:16} "
              f"{blocks:22} {('✓' if c['in_library'] else '✗'):>3} "
              f"{('✓' if c.get('stable') else '✗'):>4}")


def main():
    print(f"alchemy 内核 v{alchemy.__version__}  仓库根={REPO}")
    demo_simulate()
    demo_geometry()
    demo_catalog()
    demo_classify()
    print("\n完成。")


if __name__ == "__main__":
    main()
