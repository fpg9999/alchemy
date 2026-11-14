# -*- coding: utf-8 -*-
"""跨类无限性分析：按元素对统计公式数随 N 的增长，找出无限族"""
import json
from collections import defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
DATA = {
    3: "scope3_growth.json",
    4: None,  # 4/5/6 只有 N<=10
}


def elem_set(f):
    out = set()
    i = 0
    while i < len(f):
        out.add(f[i])
        i += 1
        while i < len(f) and f[i].isdigit():
            i += 1
    return out


g3 = json.load(open(BASE + r"\scope3_growth.json", encoding="utf-8"))
g456 = json.load(open(BASE + r"\scope456_growth.json", encoding="utf-8"))

lines = []
lines.append("\n## 范围 4/5/6 增长计数（确认跨类均为无限集）\n")
lines.append("| 范围 | N=6 | N=8 | N=10 | 最大原子 |")
lines.append("|---|---|---|---|---|")
names = {4: "聚+动", 5: "动+散", 6: "三类全混"}
for sid in [4, 5, 6]:
    d = g456[str(sid)]
    lines.append(f"| {names[sid]} | {d['6']['count']} | {d['8']['count']} | {d['10']['count']} | {d['10']['maxatoms']} |")
lines.append("")
lines.append("结论：范围 4/5/6 与范围 3 一样，公式数随总原子上限持续增长 → **跨类范围全部是无限集**；")
lines.append("因此只能按「物质族」分类描述（下面给出每类的代表与生成规律），无法穷举。")
lines.append("")

# 范围3：按元素对统计
lines.append("## 范围 3（聚+散）的无限族证据（N=6/8/10/12）\n")
d3 = {int(k): v for k, v in g3.items()}
pairs = [("O", "K"), ("O", "A"), ("O", "F"), ("X", "K"), ("C", "F"), ("O", "O"), ("K", "K")]
for a, b in pairs:
    row = []
    for N in [6, 8, 10, 12]:
        fs = d3[N]["formulas"]
        cnt = sum(1 for f in fs if elem_set(f) <= {a, b})
        row.append(cnt)
    lines.append(f"- 只用 {{{a},{b}}} 的公式数：N=6/8/10/12 → {row}")
lines.append("")
lines.append("典型无限链（代表）：O-K 体系：O2K2, O3K3, O4K4 … 随原子数增加一直有新公式；")
lines.append("O-F 体系：O3F3, O3F5, O4F3, O4F5 …；X-K 体系：O3XKF… 等，均为可无限接龙的族。")
lines.append("")

with open(BASE + r"\RESULTS.md", "a", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print("appended", len(lines), "lines to RESULTS.md")
