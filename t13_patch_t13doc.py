# -*- coding: utf-8 -*-
import io

p = r"G:\AI work\deepseek\work1\alchemy\T13_OFFICIAL_RULES.md"
s = io.open(p, encoding="utf-8").read()
anchor = "   - 旧目录 `t4_catalog_le16.json`（规则 1~8 + tied[0] 口径）与新目录公式集相同，"
new = ("   - 与旧口径（`pot_all`：规则 1~8 + tied[0]）逐投料对比：T=3..9 共 24,153 个投料中有 **50 个**产物\n"
       "     分子式多重集不同（T=7: 3、T=8: 19、T=9: 28），但 ≤16 目录的**公式集完全不变**\n"
       "     （这些差异都被其它投料覆盖）；\n" + anchor)
assert anchor in s
s = s.replace(anchor, new, 1)
io.open(p, "w", encoding="utf-8").write(s)
print("T13 updated")
