# -*- coding: utf-8 -*-
"""涌现原型演示：L1 分子 → L2 组装体 → L3 器官 → L4 生命判据（只读观测）。

运行（在仓库根目录）：
    python examples/emergence_demo.py --sample 600 --steps 600
    python examples/emergence_demo.py --sample 6000 --steps 1200 --out out.json

说明：本 demo 只调用 ``alchemy.emergence.run_experiment``，不写任何生命标志；
JSON 输出可用于与 ``intake/emergence_spec.md`` §8.3 的预注册分布对照。
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from alchemy import emergence  # noqa: E402


def default_side(n: int) -> int:
    """按 spec 的密度 ρ=N·footprint/L² ≈ 0.23 反推世界边长（N=6000 → 160）。"""
    return max(24, int(round(math.sqrt(max(1, n) / 0.234))))


def human_summary(out: dict) -> None:
    sz = out["asm_size"]
    print("=" * 64)
    print("涌现原型 demo")
    print("=" * 64)
    print(f"  seed={out['seed']}  molecules={out['molecules']}  dropped={out['dropped']}  t={out['t']}")
    print(f"  bonds={out['bond_count']}  键/分子={out['bond_count'] / max(1, out['molecules']):.2f}  "
          f"能量均值={out['energy_mean']}")
    print(f"  组装体={out['assemblies']}  组装率={out['assembly_rate']}%  "
          f"尺寸(中位/p90/最大)={sz['median']}/{sz['p90']}/{sz['max']}")
    print(f"  器官={out['organs']}  器官/组装体={out['organs_per_asm']}  "
          f"器官类型={out['organ_kinds_hist']}")
    print(f"  器官系统={out['systems']}  cycle_rank={out['system_cycle_rank']}")
    print(f"  判据通过率(%)={out['rates']}")
    print(f"  四档={out['tiers']}")
    print(f"  elapsed={out['elapsed_s']}s  digest={out['digest']}")
    print("-" * 64)
    print("  注：生命档位只由 life_report（纯读观测窗口）给出；无器官系统时大多落"
          "\u201c无机晶体/活性无机\u201d。")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="涌现原型 demo（纯标准库）")
    ap.add_argument("--sample", type=int, default=600, help="抽样分子数（默认 600）")
    ap.add_argument("--steps", type=int, default=600, help="仿真步数（默认 600）")
    ap.add_argument("--seed", type=int, default=20261119, help="随机种子")
    ap.add_argument("--L", type=int, default=None, help="世界边长；缺省按密度反推")
    ap.add_argument("--params", default=None, help="参数 JSON（缺省 alchemy/data/emergence_params.json）")
    ap.add_argument("--out", default=None, help="把完整 JSON 结果写入该文件")
    ap.add_argument("--quiet", action="store_true", help="只输出 JSON")
    args = ap.parse_args(argv)

    t0 = time.time()
    P = emergence.load_params(args.params)
    P.update({"N": args.sample, "steps": args.steps,
              "L": args.L if args.L else default_side(args.sample)})
    records = emergence.sample_records(args.sample, args.seed)
    out = emergence.run_experiment(records, args.seed, P)
    out["cli"] = {"sample": args.sample, "steps": args.steps, "L": P["L"],
                  "wall_s": round(time.time() - t0, 2)}

    payload = json.dumps(out, ensure_ascii=False, sort_keys=False)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
    if args.quiet:
        print(payload)
        return 0
    human_summary(out)
    if args.out:
        print(f"  完整 JSON 已写入 {args.out}")
    else:
        print("  JSON:", payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
