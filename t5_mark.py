# -*- coding: utf-8 -*-
"""t5_mark：把 T5 进展写回到 T4 文档的显著位置。"""
import io

BASE = r"G:\AI work\deepseek\work1\alchemy"


def append(path, text):
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(text)
    print("appended:", path.split("\\")[-1])


append(BASE + r"\T4_PROOF_ATTEMPT.md", """

---

## T5 后续进展（2026-11-12，重要更正）

- 本文件 §4.7 的「6 级结束组件 ≤7」**被更正**：穷举计数网格（各 ≤30）与随机大计数显示
  6 级组件上界为 **13**，反例模板 `O4P7K2`（穷举结果见 `T5_PROGRESS.md`、`t5_level6*.json`）。
- 新增严格引理 T1：6 级结束时最多一个类型的 3 价原子仍活跃（证明见 `T5_PROGRESS.md` §0）。
- 新增计算结构事实：6 级闭环组件只能是二聚体；单组件活跃原子 ≤7；模板库（计数 ≤18）38 种形态。
- 纯大类子反应（L2）：计数各 ≤35 穷举验证最大分子 = 9。
- 模板接龙实验：13 原子模板只会复制、不增长。
- 结论不变：**仍为条件性证明 + 强证据**；缺口仍是 L3（及 L1/L2 的一般化）。详见 `T5_PROGRESS.md`。
""")

append(BASE + r"\T4_FINAL_REPORT.md", """

---

## 补充：T5 进一步推进（2026-11-12）

- 有限性证明的后续工作见 `T5_PROGRESS.md`：更正了 6 级组件上界（7 → 13，模板 O4P7K2）、
  新增严格引理 T1、6 级模板库结构、L2 穷举验证、模板接龙反增长实验。
- 状态仍为「条件性证明 + 强数值证据」，无条件形式证明的缺口（L3）未闭合。
""")
