# -*- coding: utf-8 -*-
"""t6_fix_notes：更正 T4/T5 文档里关于猜想 D 的过时表述。"""
import io

BASE = r"G:\AI work\deepseek\work1\alchemy"

p1 = BASE + r"\T5_PROGRESS.md"
s = io.open(p1, encoding="utf-8").read()
old1 = "新猜想 D：反应全过程中每组件 `rem>=2` 原子数 <= 3（穷举 + 大规模 + 随机并列验证；两个前置引理已证）。"
new1 = ("**更正**：T6 曾提出「每组件 rem>=2 原子数 <= 3」，但该猜想**已被反例推翻**（h=4，投料 "
        "[1,2,3,6,2,6,2,0,8]）。修订后的候选是「每组件 Σ(rem-1) <= 4」；详见 T6_PROGRESS.md（修订版）。")
if old1 in s:
    s = s.replace(old1, new1)
    io.open(p1, "w", encoding="utf-8").write(s)
    print("fixed T5")

p2 = BASE + r"\T4_PROOF_ATTEMPT.md"
s = io.open(p2, encoding="utf-8").read()
old2 = ("新猜想 D：每组件 `rem>=2` 原子数 <= 3（穷举/大规模/随机并列验证）；已证两个前置引理\n"
        "  （rem=3 原子必孤立；2 价 rem=2 必孤立）。详见 `T6_PROGRESS.md`。")
new2 = ("**更正**：T6 的猜想 D（每组件 rem>=2 原子数 <= 3）**已被反例推翻**（h=4）。修订后的候选是\n"
        "  「每组件 Σ(rem-1) <= 4」。详见 `T6_PROGRESS.md`（修订版）。")
if old2 in s:
    s = s.replace(old2, new2)
    io.open(p2, "w", encoding="utf-8").write(s)
    print("fixed T4")
