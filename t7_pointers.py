# -*- coding: utf-8 -*-
"""t7_pointers：把最新交接文档入口写回 TASK3_HANDOFF.md / RESULTS.md 顶部。"""
import io

BASE = r"G:\AI work\deepseek\work1\alchemy"

note = """# 交接入口（最新）

> **新会话请先读 `PROJECT_HANDOFF.md`**（项目总交接：规则摘要、代码/数据/文档清单、
> 当前权威结论、重大修正记录、有限性证明状态与待办、复现命令）。
> 本文件保留为历史过程记录。
"""

for fn in ("TASK3_HANDOFF.md",):
    p = BASE + "\\" + fn
    s = io.open(p, encoding="utf-8").read()
    if s.startswith("# 交接入口（最新）"):
        print("already:", fn)
        continue
    io.open(p, "w", encoding="utf-8").write(note + "\n" + s)
    print("prepended pointer to", fn)

# RESULTS.md 只在末尾追加指向
p = BASE + r"\RESULTS.md"
s = io.open(p, encoding="utf-8").read()
tail = "\n\n---\n\n## 最新交接文档\n\n> 全部成果与状态已整理到 `PROJECT_HANDOFF.md`（详细版）。本文件仅保留历史过程记录。\n"
if "PROJECT_HANDOFF.md" not in s:
    io.open(p, "a", encoding="utf-8").write(tail)
    print("appended pointer to RESULTS.md")
else:
    print("RESULTS.md already has pointer")
