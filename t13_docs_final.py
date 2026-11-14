# -*- coding: utf-8 -*-
"""t13_docs_final：把规则 9 正式纳入后的数据/文档状态写入 HANDOFF 与 PROJECT_HANDOFF。"""
import io

BASE = r"G:\AI work\deepseek\work1\alchemy"


def patch(path, pairs):
    s = io.open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, "NOT FOUND in %s: %s" % (path, old[:50])
        s = s.replace(old, new, 1)
    io.open(path, "w", encoding="utf-8").write(s)
    print("updated", path.split("\\")[-1])


# 1) HANDOFF.md §11 第8条补充目录结论
patch(BASE + r"\HANDOFF.md", [
    ("   不能与旧数据混用。规则 9 实测消除并列歧义（见 `T12_RULE9E.md`）。",
     "   不能与旧数据混用。规则 9 实测消除并列歧义（见 `T12_RULE9E.md`）。\n"
     "   已用 `pot_v3` 重跑 ≤16 原子目录：`t4_catalog_le16_rule9.json`（82,961 条，与旧口径公式集完全一致，\n"
     "   一锅复现 82,961/82,961 通过）；84 三元组等大范围数据仍待重跑（见 `T13_OFFICIAL_RULES.md`）。"),
])

# 2) PROJECT_HANDOFF.md 数据行 / 文档索引
patch(BASE + r"\PROJECT_HANDOFF.md", [
    ("| `t4_catalog_le16_rule9.json` | 用正式模拟器 `pot_v3`（规则 1~9）重跑的 ≤16 原子目录 | 规则 9 新口径（重跑生成） |",
     "| `t4_catalog_le16_rule9.json` | 用正式模拟器 `pot_v3`（规则 1~9）重跑的 ≤16 原子目录 | **82,961 条**（与旧口径公式集完全一致；一锅复现 82,961/82,961 ✅） |"),
    ("`T11_RULE9D.md`（规则 9 再优化：大类数+大类原子数验证）、`T12_RULE9E.md`（规则 9 元素优先级版：实测无残余歧义）",
     "`T11_RULE9D.md`（规则 9 再优化：大类数+大类原子数验证）、`T12_RULE9E.md`（规则 9 元素优先级版：实测无残余歧义）、`T13_OFFICIAL_RULES.md`（**规则 9 正式纳入 · 正式模拟器 pot_v3 · 数据重算状态**）"),
])

# 3) PROJECT_HANDOFF.md 4.2 标题前补充旧口径说明
s = io.open(BASE + r"\PROJECT_HANDOFF.md", encoding="utf-8").read()
old = "### 4.2 旧数据（保留作过程/对照，勿作结论）"
new = ("### 4.2 旧数据（保留作过程/对照，勿作结论）\n\n"
       "> 注意：`t4_*` 系列里的旧目录/三元组/合并目录是规则 1~8 + tied[0] 口径；\n"
       "> 规则 9 正式纳入后，≤16 目录已重算（公式集与旧完全一致），其余（三元组/合并/分类表）待重跑。\n")
assert old in s
s = s.replace(old, new, 1)
io.open(BASE + r"\PROJECT_HANDOFF.md", "w", encoding="utf-8").write(s)
print("updated PROJECT_HANDOFF.md (4.2 note)")
