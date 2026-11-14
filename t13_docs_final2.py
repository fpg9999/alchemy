# -*- coding: utf-8 -*-
"""t13_docs_final2：PROJECT_HANDOFF 的剩余更新（数据行、4.2 说明、文档表、typo）。"""
import io

p = r"G:\AI work\deepseek\work1\alchemy\PROJECT_HANDOFF.md"
s = io.open(p, encoding="utf-8").read()

pairs = [
    # 数据行
    ("| `t4_catalog_le16_rule9.json` | 用正式模拟器 `pot_v3`（规则 1~9）重跑的 ≤16 原子目录 | 规则 9 新口径（重跑生成） |",
     "| `t4_catalog_le16_rule9.json` | 用正式模拟器 `pot_v3`（规则 1~9）重跑的 ≤16 原子目录 | **82,961 条**（与旧口径公式集完全一致；一锅复现 82,961/82,961 ✅） |"),
    # 4.2 说明
    ("### 4.2 旧数据（保留作过程/对照，勿作结论）",
     "### 4.2 旧数据（保留作过程/对照，勿作结论）\n\n"
     "> 注意：`t4_*` 系列里的旧目录/三元组/合并目录是规则 1~8 + tied[0] 口径；\n"
     "> 规则 9 正式纳入后，≤16 目录已重算（公式集与旧完全一致），其余（三元组/合并/分类表）待重跑。\n"),
    # 文档表：追加 T7~T13
    ("| `T6_PROGRESS.md` | ✅ 权威（证明·T6 修订版） | 规则 4~8 必要性、并列稳健、猜想 D 更正、候选 E |",
     "| `T6_PROGRESS.md` | ✅ 权威（证明·T6 修订版） | 规则 4~8 必要性、并列稳健、猜想 D 更正、候选 E |\n"
     "| `T7_TIE_EXAMPLES.md` | ✅ 权威（并列歧义例子） | 并列裁决敏感的具体例子与统计 |\n"
     "| `T8_RULE9.md` | ✅ 参考（规范决胜方案） | 规范形/规范编号兜底规则（100% 消歧的理论方案） |\n"
     "| `T9_RULE9B.md` / `T10_RULE9C.md` / `T11_RULE9D.md` | ✅ 参考（规则 9 迭代记录） | 用户各版规则 9 的验证与残余分析 |\n"
     "| `T12_RULE9E.md` | ✅ 权威（规则 9 验证） | **最终采用的规则 9（元素优先级）验证：实测无残余歧义** |\n"
     "| `T13_OFFICIAL_RULES.md` | ✅ 权威（规则 9 纳入） | 正式规则 9、正式模拟器 pot_v3、数据重算状态 |"),
    # typo
    ("（离子逐根校验通过，见旧 `verify_dong.py` 等）",
     "（几何逐根校验通过，见旧 `verify_dong.py` 等）"),
]

for old, new in pairs:
    assert old in s, "NOT FOUND: " + old[:50]
    s = s.replace(old, new, 1)

io.open(p, "w", encoding="utf-8").write(s)
print("PROJECT_HANDOFF.md updated")
