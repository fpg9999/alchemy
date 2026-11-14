# -*- coding: utf-8 -*-
"""t12b_report.py —— 由 t12b_summary.json 生成 T12B_PAIRWISE.md。"""
import json

BASE = r"G:\AI work\deepseek\work1\alchemy"
S = json.load(open(BASE + r"\t12b_summary.json", encoding="utf-8"))


def pct(x):
    return f"{x*100:.2f}%"


def num(x):
    return f"{x:,}"


def tbl(rows, cols, aligns=None):
    """rows: list of list; cols: list of titles"""
    aligns = aligns or ["---"] * len(cols)
    out = ["| " + " | ".join(cols) + " |",
           "|" + "|".join(aligns) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def fmt_pairs_examples(lst, kind):
    lines = []
    for e in lst:
        if kind == "fail":
            extra = ""
            if e.get("leftover"):
                extra = "，剩 " + "+".join(f"{k}×{v}" for k, v in e["leftover"].items())
            lines.append(f"- `{e['A']} + {e['B']}` → 失败（元素 {e['element_set']}，"
                         f"大类 {e['cats']}，三价 {e['trivalent']}，价数和 {e['total_valence']}，"
                         f"{e.get('reason','')}{extra}）")
        elif kind == "inert":
            lines.append(f"- `{e['A']} + {e['B']}` → {' + '.join(e['products'])}（原样返回）")
        elif kind == "single":
            lines.append(f"- `{e['A']} + {e['B']}` → **{e['product']}**")
    return "\n".join(lines)


def main():
    cls = S["classification"]
    n = S["n_S"]
    nv = S["n_uniq_vec"]
    tp = S["n_pairs"]
    L = []
    A = L.append

    A("# T12B · 全物质（小分子完整集）两两反应规律")
    A("")
    A("> 生成：`t12b_report.py`；数据：`t12b_summary.json`；目录：`G:\\AI work\\deepseek\\work1\\alchemy`")
    A("> 口径：主统计 = `pot_all.simulate`（规则 1~8 + tied[0]，与 T11/T11B 数据一致）；"
      "另用正式模拟器 `pot_v3`（规则 1~9）全量对照（见 §11）。")
    A("")
    A("## 0. 摘要")
    A("")
    A(f"- **|S| = {num(n)}**：`t4_catalog_all_validated.json` 中 natoms ≤ 8 的全部物质（公式去重）。")
    A(f"- **全部无序对（含 A+A）= {num(tp)} 对**；按「反应只由总向量决定」压缩为 "
      f"**{num(nv)} 个唯一总向量**（压缩 {S['vec_compression']:.2f}×），结果按类缓存。")
    A(f"- 成功 {num(cls['success'])}（{pct(cls['success_rate'])}）；失败 {num(cls['fail'])}（{pct(cls['fail_rate'])}）；"
      f"惰性 {num(cls['inert'])}（{pct(cls['inert_rate'])}）；单产物 {num(cls['single'])}（{pct(cls['single_rate'])}）；"
      f"多产物 {num(cls['multi'])}（{pct(cls['multi_rate'])}）。")
    A(f"- 单产物 **全部满足 vC = vA + vB**（违例 {S['single_product']['product_vec_equals_sum_bad']} 个）；"
      f"产物总原子数守恒（违例 {S['product_size']['conservation_bad_pairs']} 对）。")
    A(f"- 等价类：{num(S['equivalence']['n_multi_classes'])} 个类含 ≥2 对，最大类 {num(S['equivalence']['max_class_size'])} 对；"
      f"抽 {S['equivalence']['n_sample_classes']} 个类、{num(S['equivalence']['n_pairs_recomputed'])} 对独立复算，"
      f"**同向量结果全部相同**（不一致 {S['equivalence']['n_recompute_mismatch']}，多结果类 {S['equivalence']['n_multi_outcome']}）。")
    r9 = S.get("rule9")
    if r9:
        A(f"- 规则 9（pot_v3）与主口径差异：{num(r9['n_diff_vec'])}/{num(nv)} 个向量、"
          f"{num(r9['n_diff_pairs'])}/{num(tp)} 对（{pct(r9['rate_pairs'])}），对全局统计影响极小（见 §11）。")
    if cls.get("unresolved"):
        A(f"- 未判定（embedding 节点超时后仍超限）：{num(cls['unresolved'])} 对（{pct(cls['unresolved_rate'])}），单列不计入失败。")
    A("")

    # ---------------- 1. 方法与口径 ----------------
    A("## 1. 方法与口径")
    A("")
    A("### 1.1 集合 S")
    A("")
    A("- 从 `t4_catalog_all_validated.json` 的轻量索引 `t4_catalog_index.json` 取 natoms ≤ 8 的记录，"
      "按分子式去重；逐条与目录的 `atoms` 字段核对元素向量（0 缺失、0 不一致）。")
    A("- natoms 分布：")
    A("")
    nh = S["natoms_hist"]
    A(tbl([[k, num(v)] for k, v in nh.items()], ["natoms", "物质数"]))
    A("")
    A(f"- |S| = {num(n)} ≥ 3,000，按任务口径**不扩展**到 natoms≤9/10（若扩展：≤9 为 6,486 个物质、约 2.1×10⁷ 对；"
      "≤10 为 10,233 个物质、约 5.2×10⁷ 对，计算量各增 2.7×/6.8×，本任务不需要）。")
    A("### 1.2 反应定义")
    A("")
    A("- R(A,B)：把 A、B 的全部原子拆开投锅，按规则 1~8 逐根贪心成键；"
      "成功需所有原子价数填满、且每个产物分子经 `pot_v2`/`t12b_embed` 严格校验可在六边形格上摆放；"
      "任一不满足则整锅失败。产物按分子式多重集记录。")
    A("- `t12b_embed`：从 `pot_v2.embed_mol2` 复制并加状态（ok / fail / timeout）与节点上限 "
      "`CAP=300,000`；超时向量记录为「未判定」，再用 3×10⁶、1.2×10⁷ 节点上限复核（结果见 §3.1）。")
    A("- 已知定律（本任务再次验证）：**反应结果只由总向量 vA+vB 决定**。因此只需计算全部唯一总向量，"
      "再把 7.73M 对映射到结果；§5 用 50 个等价类独立复算验证该定律。")
    A("- 每对的记录格式：`t12b_shards/pairs_XXXXX.jsonl`，每行 `[i, j, ridx]`（i≤j 为 S 下标，"
      "ridx 指向唯一向量结果），共 10,000 对/片；汇总见 `t12b_pairs.jsonl`。")
    A("")
    A("### 1.3 试跑测速与全量耗时")
    A("")
    A("- **试跑**：随机抽 2,000 个总向量测速 → `pot_all` 2.0 ms/向量、`pot_v3` 3.3 ms/向量（未加 embedding 上限）；"
      "又抽 5,000 个向量（约全量的 1/130）测 embedding 尾部 → 发现大分子图回溯很慢（个别 >6 s），"
      "据此加节点上限并把超时单列，避免误判。")
    A("- **全量**：656,343 个唯一向量，16 进程分块计算，`pot_all` 口径 **570 s**（含 embedding 校验）；"
      "`pot_v3` 对照 410 s；timeout 高上限复核 570 s（282 个向量，246 个判定为可摆）；分析 23 s。")
    A("")
    A("### 1.4 运行环境")
    A("")
    A(f"- 16 进程 multiprocessing；唯一向量 {num(nv)} 个；分析脚本 `t12b_analyze.py`。")
    A("")

    # ---------------- 2. 分类统计 ----------------
    A("## 2. 结果分类总表")
    A("")
    rows = [
        ["失败（不相容）", num(cls["fail"]), pct(cls["fail_rate"])],
        ["惰性（产物=反应物多重集）", num(cls["inert"]), pct(cls["inert_rate"])],
        ["单产物（化合 A+B→C）", num(cls["single"]), pct(cls["single_rate"])],
        ["多产物（复分解/重组）", num(cls["multi"]), pct(cls["multi_rate"])],
    ]
    if cls.get("unresolved"):
        rows.append(["未判定（超时）", num(cls["unresolved"]), pct(cls["unresolved_rate"])])
    rows.append(["**合计**", f"**{num(tp)}**", "100%"])
    A(tbl(rows, ["类别", "对数", "占比"], ["---", "---:", "---:"]))
    A("")
    A("要点：")
    A("")
    A(f"- 绝大多数混合对都**成功**（{pct(cls['success_rate'])}）；失败仅 {pct(cls['fail_rate'])}。")
    A(f"- 成功中**多产物占绝对多数**（{pct(cls['multi_rate'])}），单产物只有 {pct(cls['single_rate'])}，"
      f"惰性 {pct(cls['inert_rate'])}：小分子两两混合基本都会重组，真正的「直接化合」是少数。")
    A("")

    # ---------------- 3. 失败 ----------------
    fa = S["fail_analysis"]
    fr = fa["reason"]
    A("## 3. 失败对分析")
    A("")
    A("### 3.1 失败原因分解")
    A("")
    A("| 原因 | 对数 | 说明 |")
    A("|---|---:|---|")
    if fr.get("odd_valence_pairs") is not None:
        A(f"| 价数总和为奇数 | {num(fr['odd_valence_pairs'])} | 定义上不可能接满（奇偶性） |")
        A(f"| 贪心剩键（偶价数但未接满） | {num(fr['stuck_pairs'])} | 规则 1~8 走到无候选仍 rem>0 |")
        A(f"| 产物无法摆放 | {num(fr['embed_fail_pairs'])} | rem 全 0，但产物图在六边形格上摆不出 |")
    A(f"| 未判定（超时） | {num(cls.get('unresolved', 0))} | embedding 节点超上限，单列 |")
    A("")
    A("> 注意：任一合法物质的价数总和 = 2×键数，必为偶数；因此**两个合法物质混合后的总价数一定为偶数**。"
      "本数据中奇数价数对 = 0，即**不存在「价数奇偶」导致的失败**——全部失败都来自贪心的动力学截断或几何限制。")
    A("")
    if fr.get("stuck_by_leftover_signature"):
        A("**「贪心剩键」的剩余元素签名（对数）**：")
        A("")
        A(tbl([[x["leftover"], num(x["pairs"])] for x in fr["stuck_by_leftover_signature"][:15]],
              ["剩余元素×剩余键数", "对数"], ["---", "---:"]))
        A("")
        if fr.get("stuck_uniform_rem2"):
            A("> 结构结论（重要）：**全部「剩键」失败的终态都恰好是 1 个 2 价原子（X 晶 / W 流 / A 气）"
              "完全没有成键（该原子 rem=2，其余原子全部饱和）**——"
              "穷举 11,450 个剩键失败向量，结构签名 100% 为 (剩余键总数=2, 单原子剩余=2, 剩余元素数=1)，无例外。"
              "即：规则 1~8 的贪心在「小分子二聚体 + 3 原子小分子」等配比下会把某个 2 价原子晾在一边。")
            A("")
        if fr.get("stuck_examples"):
            A("剩键失败例：")
            A("")
            for e in fr["stuck_examples"][:10]:
                A(f"- `{e['A']} + {e['B']}`（元素 {e['element_set']}，剩 {e['leftover']}，类内 {e['pairs_in_class']} 对）")
            A("")
    A("### 3.2 按三价元素个数")
    A("")
    tr = fa["by_trivalent"]
    A(tbl([[x["trivalent"], num(x["pairs"]), num(x["fail"]), pct(x["fail_rate"])] for x in tr],
          ["三价原子数（O+P+K）", "对数", "失败", "失败率"],
          ["---:", "---:", "---:", "---:"]))
    A("")
    A("失败率随三价原子数总体上升（0→0，9→3.1%，12→9.3%）；三价原子极多（≥13）时样本少且配比特殊，失败率回落。")
    A("")
    A("### 3.3 按大类组合")
    A("")
    A(tbl([[x["key"], num(x["pairs"]), pct(x["fail_rate"]), pct(x["inert_rate"]),
            pct(x["single_rate"]), pct(x["multi_rate"])] for x in fa["by_cats"]],
          ["出现的大类", "对数", "失败", "惰性", "单产物", "多产物"],
          ["---", "---:", "---:", "---:", "---:", "---:"]))
    A("")
    A("### 3.4 按总原子数")
    A("")
    A(tbl([[x["key"], num(x["pairs"]), pct(x["fail_rate"]), pct(x["inert_rate"]),
            pct(x["single_rate"]), pct(x["multi_rate"])] for x in fa["by_natoms"]],
          ["总原子数", "对数", "失败", "惰性", "单产物", "多产物"],
          ["---:", "---:", "---:", "---:", "---:", "---:"]))
    A("")
    A("> 小总原子数（4~7）的失败率反而最高（T=5 达 8.5%）：这些对由「二聚体 + 3 原子小分子」构成，"
      "正是经典的不相容组合（如 `C2+OXC`、`K2+OK`）；随总原子数增大，失败率降到 1~2%，"
      "但惰性率也从 45% 降到 1.6%、多产物率升到 86%——小混合物容易「不动」，大混合物几乎必然复分解。")
    A("")
    A(f"### 3.5 典型失败对（{len(S['examples']['fail'])} 例：按剩余原子分层 + 摆放失败）")
    A("")
    A(fmt_pairs_examples(S["examples"]["fail"], "fail"))
    A("")

    # ---------------- 4. 单产物 ----------------
    sp = S["single_product"]
    A("## 4. 单产物对（化合）")
    A("")
    A(f"- 单产物对 **{num(cls['single'])}**（{pct(cls['single_rate'])}）；涉及 "
      f"**{num(sp['n_distinct_products'])}** 种不同产物。")
    A(f"- **vC = vA + vB 验证**：全部单产物向量加法违例 {sp['product_vec_equals_sum_bad']} 个"
      f"（{'全部满足' if sp['product_vec_equals_sum_bad']==0 else '见 bad_examples'}）。")
    nic = sp.get("not_in_catalog_products", {})
    gap = None
    import os
    if os.path.exists(BASE + r"\t12b_catalog_gap.json"):
        gap = json.load(open(BASE + r"\t12b_catalog_gap.json", encoding="utf-8"))
    if nic:
        A(f"- 与 ≤16 原子完备目录交叉核对：**{len(nic)} 种**产物分子式不在 `t4_catalog_all_validated.json` 中"
          f"（共出现 {num(sum(nic.values()))} 次）。原因不是反应产物非法，而是目录枚举时 embedding 搜索预算 40 万节点"
          "对个别大分子不够（见下）。")
        if gap:
            nok = gap["checked"] - gap.get("n_fail", 0)
            caps = gap.get("caps", {})
            A(f"  - 复核（`t12b_verify_catalog.py`，用 `pot_v2.embed_mol2` + `validate_place` 提高上限）："
              f"**{nok}/{gap['checked']} 种在更高节点上限下可严格摆放**"
              f"（所需上限分布：{caps}；仍失败 {gap.get('n_fail',0)} 种）。")
        else:
            A("  - 复核脚本 `t12b_verify_catalog.py` 结果见 `t12b_catalog_gap.json`。")
    else:
        A("- 全部产物分子式都在 ≤16 原子完备目录中。")
    A("")
    A("**最常被合成的产物（前 25）**：")
    A("")
    A(tbl([[x["product"], num(x["pairs"]), x["natoms"]] for x in sp["top_products"][:25]],
          ["产物", "可由多少对合成", "原子数"], ["---", "---:", "---:"]))
    A("")
    A("单产物例：")
    A("")
    A(fmt_pairs_examples(S["examples"]["single"], "single"))
    A("")

    # ---------------- 5. 等价类 ----------------
    eq = S["equivalence"]
    A("## 5. 等价类（总向量决定反应结果）")
    A("")
    A(f"- 不同总向量 **{num(eq['n_classes'])}** 个；其中含 ≥2 对的类 **{num(eq['n_multi_classes'])}** 个，"
      f"覆盖 {num(eq['pairs_in_multi_classes'])} 对（{pct(eq['pairs_in_multi_classes']/tp)}）。")
    A(f"- 最大类 **{num(eq['max_class_size'])}** 对。类规模分布（对数 → 类数）：")
    A("")
    ch = list(eq["class_size_hist"].items())
    A(tbl([[k, num(v)] for k, v in ch[:12]] + ([["…", "…"]] if len(ch) > 12 else []),
          ["类内对数", "类数"], ["---:", "---:"]))
    A("")
    A(f"- **抽检**：随机抽 {eq['n_sample_classes']} 个含 ≥2 对的类，对类内每对用 "
      f"`pot_all.simulate` + 严格摆放**独立复算**（共 {num(eq['n_pairs_recomputed'])} 对）："
      f"与缓存结果不一致 {eq['n_recompute_mismatch']} 对、类内出现不同结果 {eq['n_multi_outcome']} 个 → "
      f"**同一总向量不同投料对的结果完全相同**（总向量定律成立）。")
    A("")
    A("**最大的等价类示例**：")
    A("")
    for tc in eq["top_classes"][:6]:
        v = tc["vector"]
        es = "".join(e for e, c in zip(["O", "X", "C", "P", "W", "L", "K", "A", "F"], v) if c)
        out = tc["outcome"]
        prod = ("失败" if out[0] != 0 else " + ".join(out[1]))
        A(f"- 向量 `{v}`（元素 {es}，{tc['size']} 对）：结果 `{prod}`；"
          f"例：`{tc['pairs'][0][0]} + {tc['pairs'][0][1]}`")
    A("")

    # ---------------- 6. 多产物模式 ----------------
    A("## 6. 多产物模式（复分解/重组）")
    A("")
    A("| 模式 | 类数 | 对数 |")
    A("|---|---:|---:|")
    for pat, info in S["multi_patterns"].items():
        A(f"| {pat} | {num(info['classes'])} | {num(info['pairs'])} |")
    A("")
    for pat, info in S["multi_patterns"].items():
        if not info["examples"]:
            continue
        A(f"### {pat}（5 例）")
        A("")
        for e in info["examples"][:5]:
            A(f"- `{e['A']} + {e['B']}` → {' + '.join(e['products'])}")
        A("")

    # ---------------- 7. 产物尺寸 ----------------
    ps = S["product_size"]
    A("## 7. 产物尺寸分布与守恒")
    A("")
    A(f"- **总原子数守恒**：把每对产物各分子原子数相加，与投料总原子数比较，违例 **"
      f"{num(ps['conservation_bad_pairs'])}** 对（应为 0）。")
    A("- 每对反应产生的分子数分布：")
    A("")
    A(tbl([[k, num(v)] for k, v in ps["nprod_hist"].items()], ["产物分子数", "对数"],
          ["---:", "---:"]))
    A("")
    A("- 单个产物分子的大小分布（全部产物，按出现次数×对数加权）：")
    A("")
    A(tbl([[k, num(v)] for k, v in ps["size_hist"].items()], ["产物原子数", "出现次数"],
          ["---:", "---:"]))
    A("")

    # ---------------- 8. 排行 ----------------
    A("## 8. 物质排行（top 15）")
    A("")
    A("每个物质与全部其它物质（含自身）共 3,931 对反应，可横向比较。")
    A("")
    for key, title in [("most_inert", "① 最惰性（惰性对数最多）"),
                       ("most_fail", "② 最不相容（失败对数最多）"),
                       ("most_single", "③ 最易化合（单产物对数最多）"),
                       ("most_multi", "④ 最多产物（复分解对数最多）")]:
        A(f"### {title}")
        A("")
        A(tbl([[x["formula"], num(x["natoms"]), x["elements"], num(x["inert"]),
                num(x["fail"]), num(x["single"]), num(x["multi"])]
               for x in S["rankings"][key]],
              ["物质", "原子数", "元素", "惰性", "失败", "单产物", "多产物"],
              ["---", "---:", "---", "---:", "---:", "---:", "---:"]))
        A("")
    A("画像（由排行数据归纳）：")
    A("")
    A("- **惰性王**：多为小分子/二聚体（如单质二聚体与高对称小分子），与大量伙伴混合后原样返回；"
      "它们往往同时也能与部分伙伴化合或失败，并非化学惰性，而是「自身向量常已是最优分组」。")
    A("- **不相容王**：集中在含 O（秩，3 价）且低阶元素配比失衡的小分子（见 §3）；"
      "O 越多，越容易在贪心规则下留下剩余键。")
    A("- **化合枢纽**：多为小单质/小化合物（如 O2、X2 等），能与大量物质直接加成生成单产物。")
    A("")

    # ---------------- 9. 按元素集合 ----------------
    A("## 9. 按元素集合统计（跨元素规律）")
    A("")
    A("说明：S（natoms≤8）中的物质大多含 5~9 种元素，因此两个物质的**元素支持并集**通常很大——"
      "94% 的对同时含聚/动/散三大类（见 §3.3）。精确的「2 元素组合」对数量很少（表中样本量小），"
      "所以除了小集合表，这里给出**三价元素组合**与**单元素出现/缺席**两种更有效的跨元素切分。")
    A("")
    A("### 9.1 按三价元素组合（O/P/K 中哪些出现）")
    A("")
    A(tbl([[x["key"], num(x["pairs"]), pct(x["fail_rate"]), pct(x["inert_rate"]),
            pct(x["single_rate"]), pct(x["multi_rate"])] for x in S.get("triv_combo", [])],
          ["三价元素组合", "对数", "失败", "惰性", "单产物", "多产物"],
          ["---", "---:", "---:", "---:", "---:", "---:"]))
    A("")
    A("### 9.2 单元素出现 / 缺席对结果的影响")
    A("")
    A(tbl([[x["key"], num(x["pairs"]), pct(x["fail_rate"]), pct(x["inert_rate"]),
            pct(x["single_rate"]), pct(x["multi_rate"])] for x in S.get("elem_present", [])],
          ["混合中含该元素", "对数", "失败", "惰性", "单产物", "多产物"],
          ["---", "---:", "---:", "---:", "---:", "---:"]))
    A("")
    A(tbl([[x["key"], num(x["pairs"]), pct(x["fail_rate"]), pct(x["inert_rate"]),
            pct(x["single_rate"]), pct(x["multi_rate"])] for x in S.get("elem_absent", [])],
          ["混合中不含该元素", "对数", "失败", "惰性", "单产物", "多产物"],
          ["---", "---:", "---:", "---:", "---:", "---:"]))
    A("")
    A("### 9.3 精确元素集合（小集合样本量小，仅供参考）")
    A("")
    for size in ("1", "2", "3"):
        items = S["sets"]["by_size"].get(size, [])
        if not items:
            continue
        A(f"**{size} 元素集合（{len(items)} 个）**")
        A("")
        A(tbl([[x["key"], num(x["pairs"]), pct(x["fail_rate"]), pct(x["inert_rate"]),
                pct(x["single_rate"]), pct(x["multi_rate"])] for x in items],
              ["元素集合", "对数", "失败", "惰性", "单产物", "多产物"],
              ["---", "---:", "---:", "---:", "---:", "---:"]))
        A("")
    # 更大集合按元素数汇总
    A("### 9.4 按元素集合大小的汇总")
    A("")
    agg = {}
    for size in range(1, 10):
        items = S["sets"]["by_size"].get(str(size), [])
        if not items:
            continue
        tot = sum(x["pairs"] for x in items)
        fl = sum(x["fail"] for x in items)
        inn = sum(x["inert"] for x in items)
        si = sum(x["single"] for x in items)
        mu = sum(x["multi"] for x in items)
        agg[size] = (len(items), tot, fl, inn, si, mu)
    A(tbl([[k, num(v[0]), num(v[1]), pct(v[2] / v[1]), pct(v[3] / v[1]),
            pct(v[4] / v[1]), pct(v[5] / v[1])] for k, v in agg.items()],
          ["元素数", "集合数", "对数", "失败", "惰性", "单产物", "多产物"],
          ["---:", "---:", "---:", "---:", "---:", "---:", "---:"]))
    A("")
    A("跨元素规律（要点）：")
    A("")
    A("- **无三价元素的体系 0 失败**：三价原子数=0 的 15,400 对全部成功（与 T11 的「无三价 175 内部 0 失败」一致）。")
    A("- **失败随三价原子数增加而上升**：三价 0→0%、9→3.1%、12→9.4%；"
      "但三价原子过多（≥13）时样本少、且配比特殊，失败率回落。")
    A("- **最不相容的是「两种不同三价元素 + 高 3 价占比」的组合**：PK、OK 两元素集合失败率最高（4.65%）；"
      "按大类看，仅含「动+散」（不含聚）的对失败率 2.75%，高于「聚+动」2.19% 与「三大类齐全」1.74%。")
    A("- **O 的存在显著提高惰性/单产物**（见 9.2），X 的缺席/出现对多产物比例影响最大；"
      "W（流，2 价）与 A（气，2 价）同时缺失时失败率最低——它们是最常见的「剩余原子」元素。")
    A("- **元素越多越倾向复分解**：集合越大，单产物比例越低、多产物越高；纯大类内的对小分子更容易原样返回（惰性）。")
    A("")

    # ---------------- 10. 自对 ----------------
    sp2 = S.get("self_pairs", {})
    if sp2:
        A("## 10. A + A 自身对")
        A("")
        name = {"inert": "惰性（2A→A+A）", "multi": "多产物", "single": "单产物（2A→C）",
                "fail": "失败", "unresolved": "未判定"}
        A(tbl([[name.get(k, k), num(v)] for k, v in sp2.items()], ["结果", "物质数"],
              ["---", "---:"]))
        A("")
        A(f"> 3,931 个自身对**全部成功**（0 失败）：任何物质与自身混合都能给出合法产物；"
          f"其中 {sp2.get('inert',0)} 个原样返回（惰性），其余合并/重组。")
        A("")

    # ---------------- 11. 规则9 ----------------
    if r9:
        A("## 11. 规则 9（pot_v3）对照")
        A("")
        A("- 主口径 `pot_all`（规则 1~8 + tied[0]）与正式模拟器 `pot_v3`（规则 1~9）全量对比：")
        A(f"  **{num(r9['n_diff_vec'])}/{num(nv)} 个唯一向量结果不同（{pct(r9['rate_vec'])}）**，"
          f"折合 **{num(r9['n_diff_pairs'])}/{num(tp)} 对（{pct(r9['rate_pairs'])}）**。")
        if r9.get("n_unknown_pairs"):
            A(f"  （另有 {num(r9['n_unknown_pairs'])} 对因 pot_v3 侧 embedding 超时未判定，未计入差异。）")
        A("- 差异**几乎全部**是「同样原子、同样成功/失败，但产物分组不同」（规则 9 只改并列裁决），"
          "量级远小于统计结论的变化阈值：T12B 的所有宏观比例与排行不受口径影响。"
          + (f"（{num(r9.get('n_same_ok_diff_vec',0))} 个向量只是产物分组不同；"
             f"仅 {num(r9.get('n_status_diff_vec',0))} 个向量改变了成功/失败。）"
             if r9.get("n_same_ok_diff_vec") is not None else ""))
        A("")
        A("差异示例（同一总向量两种口径的产物）：")
        A("")
        for e in r9["examples"][:8]:
            pair = e["pair"][0] if e["pair"] else ["?", "?"]
            a = e["pot_all"][1] if e["pot_all"][0] == 0 else "失败"
            b = e["pot_v3"][1] if e["pot_v3"][0] == 0 else "失败"
            A(f"- `{pair[0]} + {pair[1]}`（向量 {e['vector']}）：pot_all `{a}` vs pot_v3 `{b}`")
        A("")

    # ---------------- 12. 规律清单 ----------------
    A("## 12. 规律清单")
    A("")
    A("1. **总向量定律**：对 7.73M 对按总向量分组（656,343 类，99.6% 的对落在含 ≥2 对的类里），"
      f"抽 {eq['n_sample_classes']} 类 {num(eq['n_pairs_recomputed'])} 对独立复算，类内结果完全一致 → "
      "二元反应只取决于元素计数总和，与投料分子形式无关。")
    A("2. **成功占绝对多数（98.2%）**，失败仅 1.78%。合法物质的价数总和必为偶数，故两个合法物质混合的总价数"
      "**必为偶数**——本数据奇价数对 = 0，**不存在价数奇偶导致的失败**；全部失败来自贪心动力学截断或几何限制。")
    A("3. **「剩键」失败有统一结构**：11,450 个剩键失败向量的终态 100% 是「恰好 1 个 2 价原子（X/W/A）"
      "完全未成键、其余原子全饱和」，即贪心把某个 2 价原子晾在一边。另 2,279 个向量是「产物图摆不出」。")
    A("4. **失败率随三价原子数上升**（0 三价 → 0%；12 三价 → 9.3%）；最不相容的是「两种不同三价元素」"
      "（PK / OK 两元素混合 4.6%）。O、K 是主要「不相容」来源，W、A 是最常见的剩余原子（2 价）。")
    A(f"5. **单产物 = 严格向量加法**：{num(cls['single'])} 对单产物全部满足 vC=vA+vB（0 违例），"
      "不存在催化/取代式单产物反应。")
    A("6. **多产物是常态（76.3%）**：2×不同（交换）最多（1.96M 对），其次 3 产物（1.37M）、2×同种（归中/歧化 6,751 对）；"
      "最多的一对可产出 8 个分子。")
    A("7. **惰性与尺寸负相关**：T=8 时 45% 惰性，T=16 时仅 1.6%；大混合物几乎必然复分解（86% 多产物）。"
      "惰性王是小分子/二聚体（L2、F2、LF、C2…），它们同时也是化合枢纽。")
    A("8. **产物守恒**：产物总原子数恒等于投料原子数（0 违例）；单产物对产物原子数=两投料原子数之和。")
    A("9. **口径稳健**：规则 9 只改变约 0.4% 的对的结果（其中仅 1 个向量改变成功/失败），"
      "不改变任何宏观比例结论（§11）。")
    A("10. **目录小缺口**：212 种合法产物分子式未收录于 ≤16 目录（目录 embedding 预算 40 万节点所致），"
      "本任务用更高上限复核确认其可严格摆放——这是对既有目录的一个补充发现。")
    A("")

    # ---------------- 13. 文件 ----------------
    A("## 13. 文件与复现")
    A("")
    A("| 文件 | 内容 |")
    A("|---|---|")
    A("| `t12b_S.json` | 集合 S（3931 物质：formula/natoms/vec） |")
    A("| `t12b_results.json` | 656,343 唯一总向量的结果（pot_all 主口径） |")
    A("| `t12b_vec_v3.json` | 同上的 pot_v3（规则 1~9）结果 |")
    A("| `t12b_shards/pairs_*.jsonl` | 每对 `[i,j,ridx]`，10,000 对/片 |")
    A("| `t12b_pairs.jsonl` | 全部 7,728,346 对的汇总（同格式） |")
    A("| `t12b_summary.json` | 全部统计与示例 |")
    A("| `T12B_PAIRWISE.md` | 本报告 |")
    A("| `t12b_prep.py` / `t12b_compute2.py` / `t12b_compute_v3.py` / `t12b_timeout_fix.py` / "
      "`t12b_timeout_fix_v3.py` / `t12b_merge.py` / `t12b_failreason.py` / `t12b_shards.py` / "
      "`t12b_analyze.py` / `t12b_verify_catalog.py` / `t12b_figs.py` / `t12b_report.py` | 流程脚本 |")
    A("| `t12b_classification.png` / `t12b_product_size.png` / `t12b_sets2.png` | 图 |")
    A("")
    A("复现（PowerShell）：")
    A("")
    A("```powershell")
    A("$PY = 'C:\\Users\\123\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe'")
    A("$env:PYTHONIOENCODING='utf-8'")
    A("& $PY t12b_prep.py          # 选 S + 预统计")
    A("& $PY t12b_compute2.py      # 全量唯一向量（分块增量，16 进程）")
    A("& $PY t12b_timeout_fix.py   # timeout 向量高上限复核")
    A("& $PY t12b_merge.py         # 合并 -> t12b_results.json")
    A("& $PY t12b_compute_v3.py    # pot_v3 对照")
    A("& $PY t12b_failreason.py    # 失败原因细化")
    A("& $PY t12b_shards.py        # 分片输出")
    A("& $PY t12b_analyze.py       # 分析 -> t12b_summary.json")
    A("& $PY t12b_report.py        # 生成本报告")
    A("```")
    A("")
    A("## 14. 局限")
    A("")
    A("- 主口径为规则 1~8 + tied[0]（与 T11/T11B 数据一致）；正式规则 1~9 的差异见 §11。")
    A("- embedding 对极少数大分子图存在指数回溯；用节点上限 + 未判定单列处理（§3.1），未把超时误判为失败。")
    A("- S 按「natoms ≤ 8」选取：这是全部小分子的完整集（≤16 目录完备，≤8 的子集也因此完备）；"
      ">8 原子的物质对不在本任务范围（但产物可达 16 原子）。")
    A("")

    open(BASE + r"\T12B_PAIRWISE.md", "w", encoding="utf-8").write("\n".join(L))
    print("saved T12B_PAIRWISE.md", len(L), "lines")


if __name__ == "__main__":
    main()
