# -*- coding: utf-8 -*-
"""物质目录（catalog）：84,225 条已验证物质的只读索引。

目录文件 ``t4_catalog_all_validated.json`` 是本项目最重要的**数据资产**：每条记录是一个
"分子式 + 原子序列 + 键表 + 合法六边形摆放"，覆盖 **≤16 原子**的全部产出（82,961 条），
外加 >16 原子的抽样（最大 97 原子）。

记录字段：
    formula  分子式（官方书写顺序）
    natoms   原子数
    zh       中文名（秩晶冰 …）
    atoms    元素序列
    edges    ``[[i, j, mult], ...]`` 键表
    place    ``{"0": [q, r], ...}`` 六边形轴向坐标（可能为 None：摆放搜索失败）
    feed     9 维元素计数向量（``ORDER`` 顺序）
    source   该记录的来源标记（不同历史批次）

路径解析顺序（**不含任何硬编码绝对路径**）：
    1. 显式传入 ``path``
    2. 环境变量 ``ALCHEMY_CATALOG``
    3. 仓库根目录下的默认文件名（相对本包位置推导）

如果文件不存在（GitHub 仓库只带 ``_data_gz/`` 压缩副本），先跑仓库根的
``python unpack_data.py`` 解压。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .elements import ORDER, formula_of, parse_formula

__all__ = [
    "Catalog", "load_catalog", "get_catalog", "clear_cache",
    "DEFAULT_FILENAME", "ENV_VAR", "default_catalog_path",
]

DEFAULT_FILENAME = "t4_catalog_all_validated.json"
ENV_VAR = "ALCHEMY_CATALOG"


def default_catalog_path() -> Path:
    """推导默认目录文件路径：仓库根 / 默认文件名。

    本包位于 ``<repo>/alchemy/core/catalog.py``，因此 ``parents[2]`` 就是仓库根。
    """
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / DEFAULT_FILENAME


def _resolve_path(path=None) -> Path:
    if path is not None:
        return Path(path)
    env = os.environ.get(ENV_VAR)
    if env:
        return Path(env)
    return default_catalog_path()


class Catalog:
    """只读物质目录。构造即建索引；支持按分子式、按原子数、按元素向量查询。"""

    def __init__(self, records, path: Path | None = None):
        self._records: list[dict] = list(records)
        self.path = Path(path) if path is not None else None
        self._by_formula: dict[str, dict] = {}
        self._by_natoms: dict[int, list[dict]] = {}
        for rec in self._records:
            f = rec.get("formula")
            if f is not None and f not in self._by_formula:
                self._by_formula[f] = rec
            if "natoms" not in rec and "atoms" in rec:
                rec["natoms"] = len(rec["atoms"])
            self._by_natoms.setdefault(rec["natoms"], []).append(rec)

    # ------------------------------------------------------------ 加载
    @classmethod
    def load(cls, path=None) -> "Catalog":
        p = _resolve_path(path)
        if not p.exists():
            raise FileNotFoundError(
                f"找不到物质目录文件：{p}\n"
                f"请先在仓库根目录运行 `python unpack_data.py` 解压 _data_gz/ 中的数据，\n"
                f"或用参数 path= / 环境变量 {ENV_VAR} 指定目录文件路径。"
            )
        with open(p, encoding="utf-8") as fh:
            records = json.load(fh)
        return cls(records, path=p)

    # ------------------------------------------------------------ 容器协议
    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self):
        return iter(self._records)

    def __contains__(self, formula: str) -> bool:
        return formula in self._by_formula

    def __getitem__(self, formula: str) -> dict:
        return self._by_formula[formula]

    # ------------------------------------------------------------ 查询
    def get(self, formula: str, default=None):
        """按分子式取记录；不存在返回 ``default``。"""
        return self._by_formula.get(formula, default)

    def formulas(self) -> list[str]:
        """全部分子式（保持文件内顺序）。"""
        return [r["formula"] for r in self._records]

    def records(self) -> list[dict]:
        """全部记录（原样，勿修改）。"""
        return self._records

    def by_natoms(self, n: int) -> list[dict]:
        """恰有 n 个原子的全部记录。"""
        return self._by_natoms.get(n, [])

    def natoms_histogram(self) -> dict[int, int]:
        """原子数 -> 物质数。"""
        return {k: len(v) for k, v in sorted(self._by_natoms.items())}

    def feed(self, formula: str) -> tuple[int, ...]:
        """分子式对应的 9 维元素计数向量（``ORDER`` 顺序）。"""
        rec = self._by_formula[formula]
        if rec.get("feed"):
            return tuple(rec["feed"])
        return parse_formula(formula)

    def find_by_vec(self, vec) -> dict | None:
        """按元素计数向量精确查物质（等价于"用自身组成投料"的不动点查询）。"""
        return self._by_formula.get(formula_of(_vec_to_atoms(vec)))

    def stats(self) -> dict:
        """目录概况：总数、原子数分布、≤16 原子条数、缺失 place 的条数。"""
        hist = self.natoms_histogram()
        total = len(self._records)
        le16 = sum(c for k, c in hist.items() if k <= 16)
        no_place = sum(1 for r in self._records if not r.get("place"))
        sources: dict[str, int] = {}
        for r in self._records:
            s = r.get("source", "?")
            sources[s] = sources.get(s, 0) + 1
        return {
            "total": total,
            "natoms": hist,
            "max_natoms": max(hist) if hist else 0,
            "le16": le16,
            "over16": total - le16,
            "missing_place": no_place,
            "sources": sources,
        }


def _vec_to_atoms(vec) -> list[str]:
    out: list[str] = []
    for e, c in zip(ORDER, vec):
        out += [e] * int(c)
    return out


# ---------------------------------------------------------------- 模块级缓存
_CACHE: dict[str, Catalog] = {}


def load_catalog(path=None) -> Catalog:
    """加载目录（显式路径；不缓存）。"""
    return Catalog.load(path)


def get_catalog(path=None) -> Catalog:
    """取得目录单例（按路径缓存，重复调用只读一次磁盘）。"""
    key = str(_resolve_path(path))
    cat = _CACHE.get(key)
    if cat is None:
        cat = Catalog.load(path)
        _CACHE[key] = cat
    return cat


def clear_cache() -> None:
    """清空单例缓存（测试用）。"""
    _CACHE.clear()
