# -*- coding: utf-8 -*-
"""t7_update_handover：把并列裁决例子文档与脚本加入交接文档索引。"""
import io

p = r"G:\AI work\deepseek\work1\alchemy\PROJECT_HANDOFF.md"
s = io.open(p, encoding="utf-8").read()

s = s.replace(
    "`T5_PROGRESS.md`、`T6_PROGRESS.md`、`PROJECT_HANDOFF.md`（本文件）。",
    "`T5_PROGRESS.md`、`T6_PROGRESS.md`、`T7_TIE_EXAMPLES.md`（并列裁决具体例子）、`PROJECT_HANDOFF.md`（本文件）。",
)
s = s.replace(
    "`t5_level6.json`、`t5_level6_struct.json`、`t5_pure_聚.json`、`t5_levelbounds.json`、`t6_*.json`。",
    "`t5_level6.json`、`t5_level6_struct.json`、`t5_pure_聚.json`、`t5_levelbounds.json`、`t6_*.json`、`t7_tie_examples.json`。",
)
s = s.replace(
    "| `t6_active*.py` / `t6_highrem.py` | 活跃原子统计（早前探索） |",
    "| `t6_active*.py` / `t6_highrem.py` | 活跃原子统计（早前探索） |\n"
    "| `t7_tie_examples.py` / `t7_tie_trace.py` | 并列裁决歧义的具体例子（分支 DFS / 首次分歧定位） |",
)
io.open(p, "w", encoding="utf-8").write(s)
print("updated handover index")
