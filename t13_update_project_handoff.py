# -*- coding: utf-8 -*-
"""t13_update_project_handoff：把“规则 9 已正式纳入”的信息写进 PROJECT_HANDOFF.md。"""
import io

p = r"G:\AI work\deepseek\work1\alchemy\PROJECT_HANDOFF.md"
s = io.open(p, encoding="utf-8").read()
orig = len(s)


def rep(old, new):
    global s
    assert old in s, "NOT FOUND: " + old[:60]
    s = s.replace(old, new, 1)


# 2.3 key 公式 + 规则 9 说明
rep(
    "key = (-周期表距离, -(rem_i+rem_j), 族序, cross, 分子内距离,\n"
    "       规则5, 规则6, 规则7, 规则8)",
    "key = (-周期表距离, -(rem_i+rem_j), 族序, cross, 分子内距离,\n"
    "       规则5, 规则6, 规则7, 规则8, 规则9)",
)
rep(
    "- 详细规格与已核实的 5 个自检案例见 `HANDOFF.md` §5~§6。",
    "- **规则 9（2026-11-13 正式纳入）**：按结合后分子式内元素数量比较，优先级\n"
    "  **秩(O) > 晶(X) > 凝/冰(C) > 沌(K) > 气(A) > 焰(F) > 势(P) > 流(W) > 电(L)**（多者优先）。\n"
    "  正式模拟器 `pot_v3.py`；实测 T≤9 全量无残余歧义（`T12_RULE9E.md`）。\n"
    "- 详细规格与已核实的自检案例见 `HANDOFF.md` §5~§6。",
)

# 2.4 口径第 4 条
rep(
    "4. **并列裁决**：规则 1~8 仍有并列；约 **0.5%** 随机投料在不同并列裁决下得到不同分子式多重集。\n"
    "   本项目的目录是「`pot_all.simulate` 的确定性裁决（tied[0]）」口径；有限性结论不受影响。",
    "4. **并列裁决（已由规则 9 处理）**：规则 1~8 存在并列；**2026-11-13 起规则 9（元素优先级）正式纳入**，\n"
    "   实测 T≤9 全量无残余歧义（`T12_RULE9E.md`）。正式模拟器为 `pot_v3.py`；\n"
    "   旧目录/数据（82,961 条等）是「规则 1~8 + tied[0]」旧口径，需用 `pot_v3` 重算（见 §4.1）。",
)

# 3.1 代码表加 pot_v3
rep(
    "| `pot_all.py` | 原始通用模拟器：规则 1~8 + typed embedding | **`embed_mol` 有 bug**（见 §7.1），不要直接用于\"合法性\"判定 |",
    "| `pot_all.py` | 原始通用模拟器：规则 1~8 + typed embedding | **`embed_mol` 有 bug**（见 §7.1），不要直接用于\"合法性\"判定 |\n"
    "| `pot_v3.py` | **正式模拟器：规则 1~9**（规则 9 = 元素优先级决胜） | ★ 2026-11-13 起为权威口径；输出格式与 pot_all 一致 |",
)

# 3.2 加规则 9 验证脚本
rep(
    "| `t7_tie_examples.py` / `t7_tie_trace.py` | 并列裁决歧义的具体例子（分支 DFS / 首次分歧定位） |",
    "| `t7_tie_examples.py` / `t7_tie_trace.py` | 并列裁决歧义的具体例子（分支 DFS / 首次分歧定位） |\n"
    "| `t11_rule9d.py` / `t12_rule9e.py` / `t12_exact.py` / `t12_struct.py` / `t13_validate_v3.py` | 规则 9 各版本验证、正式模拟器一致性与压力测试 |",
)

# 4.1 数据表加规则 9 目录
rep(
    "| `t4_catalog_le16.json` | 全 9 元素 ≤16 原子完备物质目录（严格可摆 + 每条自组成复现） | **82,961 条** |",
    "| `t4_catalog_le16.json` | 全 9 元素 ≤16 原子完备物质目录（严格可摆 + 每条自组成复现） | **82,961 条**（⚠ 规则 1~8 旧口径） |\n"
    "| `t4_catalog_le16_rule9.json` | 用正式模拟器 `pot_v3`（规则 1~9）重跑的 ≤16 原子目录 | 规则 9 新口径（重跑生成） |",
)

# 7.4 追加规则 9 正式纳入说明
rep(
    "- 建议：文档/交付物中注明该口径；若要\"所有裁决并集\"，需重新枚举（工作量更大）。\n"
    "  复现：`t7_tie_examples.py`（`example`/`scan`）与 `t7_tie_trace.py`。",
    "- 建议：文档/交付物中注明该口径；若要\"所有裁决并集\"，需重新枚举（工作量更大）。\n"
    "  复现：`t7_tie_examples.py`（`example`/`scan`）与 `t7_tie_trace.py`。\n"
    "- **2026-11-13：规则 9（元素优先级版）已正式纳入规则**（`HANDOFF.md` §5 规则 9；正式模拟器 `pot_v3.py`）。\n"
    "  实测 T≤9 全量 + 大锅/结构化压力测试无残余歧义（`T12_RULE9E.md`）；旧目录需按新口径重算。",
)

io.open(p, "w", encoding="utf-8").write(s)
print("PROJECT_HANDOFF.md updated, +chars:", len(s) - orig)
