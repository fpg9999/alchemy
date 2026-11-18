# 仓库瘦身方案

> 测量时间：2026-11-18　基于 `git ls-tree -r -l origin/main`（1199 个跟踪文件）

---

## 1. 现状

| 指标 | 值 |
|---|--:|
| 跟踪内容（未压缩） | **694.3 MB / 1199 个文件** |
| `.git`（压缩后） | **173.6 MB** |
| 工作区（含被 ignore 的解压数据） | 951.9 MB |
| 最大单文件 | 39.4 MB（`_data_gz/t12b_pairs.jsonl.gz`） |

GitHub 的限制：单文件 >100MB 直接拒绝、>50MB 警告、仓库 >1GB 会提示。**当前都没超**，
但增速很危险（T64/T65/T66 三天就加了约 276MB 跟踪内容）。

## 2. 空间被谁占掉了

| 类型 | 文件数 | 大小 | 占比 |
|---|--:|--:|--:|
| **实验 `*_result.json`** | **50** | **517.7 MB** | **75%** |
| 其它 `.json` | 238 | 57.9 MB | 8% |
| `.jsonl` / `.gz` | 9 | 51.7 MB | 7% |
| `.png` | 311 | 47.9 MB | 7% |
| `*_analysis.json` | 10 | 7.7 MB | 1% |
| `.md` | 102 | 7.1 MB | 1% |
| `.py` | 442 | 4.0 MB | 0.6% |
| `*_state.json` | 33 | 0.2 MB | 0.03% |

**结论：75% 的体积是 50 个实验 result JSON，而这批文件是可以由脚本 + 种子重算的产物。**

按前缀看：`t64_*` 95MB、`t65_*` 93.8MB、`t59_*` 87.9MB、`t66_*` 86.1MB、`t62_*` 78.9MB。

最大的 5 个（合计 130.5MB）全是 `*_hf_result.json` / `*_phaseA_result.json` 这类高保真/大批次结果。

---

## 3. 四个层级的方案

### Tier 1 · 立即，零风险，不改历史

```powershell
git gc --aggressive --prune=now          # 整理 pack（本地 .git 小幅收缩）
```

其他机器拉取时用**浅克隆/部分克隆**，不必下载 174MB 的 pack：

```powershell
git clone --depth 1  https://github.com/fpg9999/alchemy.git     # 只要最新快照
# 或
git clone --filter=blob:none https://github.com/fpg9999/alchemy.git   # 按需取 blob
```

收益：小（本地几 MB）+ 新机器拉取快。
**风险：无。** 历史不动。

### Tier 2 · 向前治理，不改历史（**推荐先做**）

把 `*_result.json` 纳入项目已有的 `_data_gz/` 约定：

1. 提交前 gzip，仓库只留 `.gz` + `manifest.json`（含 SHA256 + 原始大小）；
2. `.gitignore` 增加：
   ```
   /t*_result.json
   /t*_hf_result.json
   /t*_state.json
   ```
   （保留 `_data_gz/*.gz`）
3. 扩展现有 `unpack_data.py`，支持新条目（它已经按 manifest 解压 + 校验 SHA）。

**收益**：JSON 压缩比约 **8~10:1**，所以未来每 700MB 实验数据只占 ~70MB。
**风险：无**（只影响以后的提交）。
**注意：已提交的历史不会变小。**

### Tier 3 · 改写历史，一次性彻底瘦身

用 `git filter-repo`（推荐）或 BFG 把大 blob 从历史里剥离：

```powershell
pip install git-filter-repo
git filter-repo --strip-blobs-bigger-than 5M
# 或者只删结果文件
git filter-repo --path-glob 't*_result.json' --invert-paths
git push --force origin main
```

**预计效果**：跟踪内容 694MB → ~130MB；`.git` 174MB → **~35~45MB**。

**代价（务必清楚）**：
- 全部提交哈希改变（现有 20+ 条提交重写）；
- 需要 `--force` 推送；
- **其他机器必须重新克隆**，否则历史对不上；
- GitHub 上的旧对象不会立刻消失（会保留一段时间才 GC）。

### Tier 4 · 平台侧方案

| 方案 | 说明 | 代价 |
|---|---|---|
| **Git LFS** | 大文件转 LFS 指针 | 免费 1GB 存储 + 1GB/月流量；需迁移历史 |
| **GitHub Releases** | 结果数据作为 release 附件，仓库只留 manifest | 需改工作流；附件上限 2GB/个 |
| **外部对象存储** | S3/OSS 放数据，仓库只留链接与 SHA | 需另建账号与脚本 |

---

## 4. 建议

1. **现在做 Tier 1 + Tier 2**：零风险，立刻止住增长；
2. `.git` 现在 174MB，距离 1GB 还有余量，**不必急着改历史**；
3. 等累计到 ~500MB 时（按现在增速约 2~3 周），再一次性做 Tier 3 ——
   前提是先把另外两台机器的工作合并完，因为重写后它们都要重新克隆。
4. 长期建议：**`*_result.json` 永不直接入库**，一律走 `_data_gz/` + manifest。

## 5. 一个额外的观察

`t*_state.json`（33 个，0.2MB）是"0°C 整理后的底物状态"，体积极小但**不可重算**（它是中间态），
建议保留。而 `*_result.json` 是"跑完的终态 + 时间序列"，**可重算**，优先走压缩或外置。
