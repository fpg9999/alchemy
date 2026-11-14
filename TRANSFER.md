# 跨电脑交接方案（ALCHEMY）

工作目录：`G:\AI work\deepseek\work1\alchemy`
交接入口：`HANDOFF.md`

---

## 方案 A：GitHub（推荐，日常同步最方便）

### 前提
- 已安装 git（本机 git 2.56.0）；
- 已安装 gh（本机 gh 2.103.2），但**当前未登录**；
- 仓库已本地初始化并提交（见 `git log`），但**尚未 push**。

### A1. 在旧电脑上创建远程仓库并 push

```powershell
cd "G:\AI work\deepseek\work1\alchemy"

# 登录 GitHub（按提示浏览器登录）
gh auth login

# 创建私有仓库并 push（推荐）
gh repo create alchemy --private --source=. --remote=origin --push

# 如果已经手动建好仓库，则：
# git remote add origin https://github.com/<你的用户名>/alchemy.git
# git push -u origin main
```

> 当前分支是 `main`。

### A2. 在新电脑上 clone

```powershell
git clone https://github.com/<你的用户名>/alchemy.git
cd alchemy
python unpack_data.py          # 解压 _data_gz/ 里的大文件
python -c "import pot_v3; print(pot_v3.simulate(['O','K','O']))"
```

### A3. 仓库里有什么
- 全部 `.py` 脚本、`docs/`、`images/`、`archive/`；
- `_data_gz/`：6 个大文件的 gzip（最大 41MB，低于 GitHub 100MB 单文件限制）；
- 大文件原件（`t4_catalog_all_validated.json` 等）被 `.gitignore` 排除，clone 后需 `unpack_data.py`；
- 仓库总大小约 100~150MB（含压缩数据），不需要 Git LFS。

### A4. 如果一定要把原始大文件也放进 GitHub
- 需要 Git LFS：
  ```powershell
  git lfs install
  git lfs track "t4_catalog_all_validated.json" "t12b_pairs.jsonl" ...
  ```
- 但免费 LFS 配额有限，不推荐；日常用 `_data_gz/` 已足够。

---

## 方案 B：全量 ZIP（最稳，适合 U 盘/网盘）

已生成：

```
G:\AI work\deepseek\work1\alchemy_transfer_2026-11-14.zip
```

- 包含**全部原始文件**（含大 JSON/JL），不含 `.git`、`__pycache__`、临时压缩测试目录；
- 解压后直接就是完整 `alchemy/` 目录，无需 `unpack_data.py`；
- 跨电脑：复制 zip → 解压 → 读 `HANDOFF.md`。

校验：
```powershell
Get-FileHash "G:\AI work\deepseek\work1\alchemy_transfer_2026-11-14.zip" -Algorithm SHA256
```
（SHA256 见 `alchemy_transfer_2026-11-14.sha256.txt`）

---

## 方案 C：git bundle（离线保留 git 历史）

已生成：

```
G:\AI work\deepseek\work1\alchemy_repo.bundle
```

在新电脑上：
```powershell
git clone alchemy_repo.bundle alchemy
cd alchemy
python unpack_data.py
```
bundle 不含大文件原件，clone 后同样需要 `unpack_data.py`。

---

## 方案 D：直接复制整个目录

如果只是同系统/同盘：
```
复制 G:\AI work\deepseek\work1\alchemy 到新电脑任意路径
```
注意：
- 需要把 `alchemy/` 整个目录（含 `_data_gz`、`archive`、`docs`、`images`）一起复制；
- Python 运行时路径不同不影响，脚本纯 Python + Pillow；
- 复制后读 `HANDOFF.md`，无需解压（有原始大文件）。

---

## 数据文件说明

被压缩/排除的 6 个大文件：

| 原文件 | 大小 | gzip |
|---|---:|---:|
| `t12b_pairs.jsonl` | 149MB | 41MB |
| `t4_catalog_all_validated.json` | 114MB | 4.7MB |
| `t12b_vec_v3.json` | 31MB | 3.9MB |
| `t12b_results.json` | 31MB | 3.9MB |
| `t12c_sample_pairs.json` | 8.6MB | 0.8MB |
| `t4_catalog_index.json` | 8.3MB | 0.8MB |

- `_data_gz/manifest.json` 含每个文件的原始 SHA256 与压缩后 SHA256；
- `python unpack_data.py` 会自动校验；`--force` 可覆盖。

---

## 新电脑最小检查清单

1. Python 3.10+ 可运行；
2. `pip install -r requirements.txt`（Pillow）；
3. 数据文件存在（或 `python unpack_data.py`）；
4. 冒烟测试：
   ```powershell
   python -c "import pot_v3; print(pot_v3.simulate(['O','K']))"
   ```
5. 读 `HANDOFF.md` 第 0 节的新对话启动语。
