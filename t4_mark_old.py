# -*- coding: utf-8 -*-
"""t4_mark_old：给旧文档加结论更正提示，并把最终状态写回 TASK3_HANDOFF.md / RESULTS.md。"""
import io

BASE = r"G:\AI work\deepseek\work1\alchemy"


def prepend(path, note):
    s = io.open(path, encoding="utf-8").read()
    head = note.split("\n")[0]
    if s.startswith(head):
        print("already:", path.split("\\")[-1])
        return
    io.open(path, "w", encoding="utf-8").write(note + "\n\n" + s)
    print("noted:", path.split("\\")[-1])


prepend(BASE + r"\CATALOG.md",
        "> ⛔ **本文件的分类结论已作废（2026-11-12）**：「无限 304 / 有限 207」「16 个最小无限核心」与"
        "\n> 「无限增长参数族」均已被推翻（可摆放性检查器有 bug；参数族经直接投料检验均很早封顶）。"
        "\n> 同时约 5% 的摆放坐标非法。**最终结论请看 `T4_FINAL_REPORT.md`、`T4_CLASSIFICATION.md`、`T4_CATALOG.md`。**"
        "\n> 本文件只可作为旧数据过程的参考，不要作为结论。")

prepend(BASE + r"\CLASSIFICATION_REVISED.md",
        "> ⛔ **已被 `T4_CLASSIFICATION.md` 取代**：本文件 224/287 分类基于「9 个核心三元组无限」的假设，"
        "\n> 而修复校验后所有三元组都有限（9 个核心封顶 42）。最新结论：511 类全部有限，见 `T4_FINAL_REPORT.md`。")

prepend(BASE + r"\TASK3_VERIFY.md",
        "> 说明：本文件是第一次复核（过程记录）。后续已修复可摆放性检查器的 bug 并重做全部数据，"
        "\n> 最终结论见 `T4_FINAL_REPORT.md` / `T4_CLASSIFICATION.md`。")

append = """

---

## 最终修正（T4，2026-11-12）——「真正的」511 类别分类表与有限性论证

1. **模拟器 bug**：`pot_all.embed_mol` 的 L 中间格 set 回溯 bug + `scan_league` 的规范形缓存碰撞 bug，
   导致旧目录约 5.3% 摆放非法、10 个伪物质；旧「无限族」全部是假象。
   修复版 `pot_v2.py`（embed_mol2 + validate_place）。
2. **重做数据**：
   - 全 9 元素 ≤16 原子完备目录：**82961 条**（全部严格可摆 + 全部自组成一锅复现）；
   - 84 个三元组 T≤48 **完备枚举**：4837 条（999 条 >16 原子，最大分子 42）；
   - 4~9 元类别搜索最大合法分子：4 元 57、5 元 69、6 元 82、8 元 87、全 9 元 97。
   - 合并全部已知物质：**84225 条**。
3. **511 类分类**：**全部有限**（无限 0）。完整表：`T4_CLASSIFICATION.md` / `t4_classification.json`。
4. **有限性**：条件性证明（严格归约到「单分子原子数上界」猜想）+ 6 条严格结构引理
   + 全 511 类数值证据；唯一缺口一条组合引理。详见 `T4_FINAL_REPORT.md` §4、`T4_PROOF_ATTEMPT.md`。
5. **口径**：规则 1~8 仍有并列（约 0.5% 随机投料产物不同）；物质清单是「确定并列裁决」口径。
6. 结论以 `T4_FINAL_REPORT.md` 为准；本文件此前各节的分类/无限规律均作废。
"""
with io.open(BASE + r"\TASK3_HANDOFF.md", "a", encoding="utf-8") as f:
    f.write(append)
print("appended TASK3_HANDOFF")

append2 = """

---

## T4 最终修正（2026-11-12）

- 修复可摆放性检查器（L 中点 + 缓存碰撞）后重做数据：
  - 全 9 元素 ≤16 原子完备目录 **82961 条**（全部严格可摆、全部自组成一锅复现）；
  - 84 个三元组 T≤48 完备枚举（4837 条，999 条 >16 原子，最大分子 42）；
  - 合并全部已知物质 **84225 条**；
  - 511 类别**全部有限**（旧的无限 304 / 最小无限核心 / 参数族全部作废）。
- 有限性：条件性证明 + 6 条严格结构引理 + 全 511 类数值证据；缺口见 `T4_PROOF_ATTEMPT.md`。
- 详见 `T4_FINAL_REPORT.md`、`T4_CLASSIFICATION.md`、`T4_CATALOG.md`。
"""
with io.open(BASE + r"\RESULTS.md", "a", encoding="utf-8") as f:
    f.write(append2)
print("appended RESULTS")
