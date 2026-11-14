# -*- coding: utf-8 -*-
"""t3_apply_notes：给 CATALOG.md / CLASSIFICATION_REVISED.md 加复核警告，给 RESULTS.md 追加更正小节。"""
import io
import os

BASE = r"G:\AI work\deepseek\work1\alchemy"


def prepend(path, note):
    with io.open(path, encoding="utf-8") as f:
        s = f.read()
    head = note.split("\n")[0]
    if s.startswith(head):
        print("already noted:", os.path.basename(path))
        return
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(note + "\n\n" + s)
    print("noted:", os.path.basename(path))


note_catalog = (
    "> ⚠ **复核警告（2026-11-12，接手会话）**：本文件的「无限 304 / 有限 207」「16 个最小无限类别」与\n"
    "> 「无限增长参数族」**已被证明不可靠**（参数族经直接投料检验是假的；旧判定把\"小 T 一锅一分子\"误当无限）。\n"
    "> 物质清单部分（≤16 原子全枚举 82239 条）仍然有效。请以 `TASK3_VERIFY.md` 为准。"
)
prepend(os.path.join(BASE, "CATALOG.md"), note_catalog)

note_rev = (
    "> ⚠ **已被取代**：本文件 224/287 分类基于「9 个核心三元组无限」的假设；后续精确枚举显示这些\n"
    "> 核心同样在 ~42 原子封顶（T=64；T=96 复查仍 ≤42），因此本分类同样不可靠。\n"
    "> 最终复核见 `TASK3_VERIFY.md`。"
)
prepend(os.path.join(BASE, "CLASSIFICATION_REVISED.md"), note_rev)

append = """
---

## 任务3 复核（接手会话，2026-11-12 05:20）

**重要更正**：`CATALOG.md` 的「无限 304 / 有限 207」与「16 个最小无限类别 / 参数族」**不可靠**，详见
`TASK3_VERIFY.md`。要点：

1. 旧"无限证据"（T 较小时 max=T 的一锅一分子）不能区分有限/无限：有限类别（如 X/C/K/A）在 T≤32 时
   同样 max=T，但精确枚举到 T=64 封顶 33。
2. 旧"参数族"经直接投料检验是假的：`X_mK_2` 只到 X7K2，`O_mK_{m+2}` 只到 O4K6，`O_mX_mK_{m+2}` 只到 O4X7K6。
3. 精确全枚举（T=48/56/64）给出的封顶：9 个"2 个不同大类 3 价 + 1 个 2 价"三元组为 42 原子；其余三元组 18~31；
   4 元 a=1 类（X/C/K/A）为 33；7 元 a=1 类为 ~46。
4. 全 9 元素池：已校验可摆放的最大分子为 97 原子（一锅一分子，O3X8C15P10WK36A22F2）；
   更大的 110~160 原子候选图在 30M 节点预算内未通过可摆放校验（其中一部分存在硬几何矛盾）。
5. 因此：**现有证据不支持"无限类别"；更可能是全部 511 类有限，封顶随可用元素池增大（~9 到 ~100+）。**
   旧的 304/207 与中间稿 224/287 都不可靠；`families_full.json` 与 CATALOG 的"参数族"应视为无效。

复核脚本：`t3_growth_triples.py`、`t3_triple_probe.py`、`t3_exact_growth.py`、`t3_max_search.py`、
`t3_anneal.py`、`t3_subset_anneal.py`；数据 `t3_*.json`。
"""
with io.open(os.path.join(BASE, "RESULTS.md"), "a", encoding="utf-8") as f:
    f.write(append)
print("done")
