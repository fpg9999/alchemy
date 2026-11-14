# -*- coding: utf-8 -*-
"""t6_fix_notes2：在 T4/T5 文档末尾追加对猜想 D 的更正说明。"""
import io

BASE = r"G:\AI work\deepseek\work1\alchemy"

note = """

### 更正（2026-11-12 本轮）

上一段"新猜想 D：每组件 rem>=2 原子数 <= 3"**已被反例推翻**：
投料 `[1,2,3,6,2,6,2,0,8]`（T=30）第 7 步出现 `{O(rem0), K(rem0), P×4(rem2)}`，h=4。
修订后的候选不变量为「每组件 `Σ(rem-1) <= 4`」（excess），详见 `T6_PROGRESS.md`（修订版）。
"""
for fn in ("T5_PROGRESS.md", "T4_PROOF_ATTEMPT.md"):
    with io.open(BASE + "\\" + fn, "a", encoding="utf-8") as f:
        f.write(note)
    print("appended correction to", fn)
