# -*- coding: utf-8 -*-
"""极简测试运行器（不依赖 pytest / setuptools）。

用法（在仓库根目录）：
    python tests/run_all.py            # 跑全部
    python tests/run_all.py reactor    # 只跑文件名含 "reactor" 的模块

也兼容 pytest：`pytest tests/`。
"""

import importlib
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))


def discover(filter_kw: str | None = None):
    mods = sorted(p.stem for p in HERE.glob("test_*.py"))
    if filter_kw:
        mods = [m for m in mods if filter_kw in m]
    return mods


def main(argv):
    filter_kw = argv[1] if len(argv) > 1 else None
    total = passed = 0
    failures = []
    t0 = time.time()
    for mod_name in discover(filter_kw):
        print(f"\n=== {mod_name} " + "=" * (50 - len(mod_name)))
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            total += 1
            failures.append((mod_name, "<import>", traceback.format_exc()))
            print("IMPORT FAILED")
            traceback.print_exc()
            continue
        names = [n for n in dir(mod) if n.startswith("test_") and callable(getattr(mod, n))]
        for name in sorted(names):
            total += 1
            t = time.time()
            try:
                getattr(mod, name)()
                passed += 1
                print(f"  PASS  {name}  ({time.time()-t:.2f}s)")
            except Exception as exc:
                failures.append((mod_name, name, traceback.format_exc()))
                print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")
    dt = time.time() - t0
    print("\n" + "=" * 60)
    if failures:
        print(f"{passed}/{total} passed, {len(failures)} FAILED  ({dt:.1f}s)\n")
        for mod_name, name, tb in failures:
            print(f"--- {mod_name}::{name} ---")
            print(tb)
        return 1
    print(f"ALL {total} TESTS PASSED  ({dt:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
