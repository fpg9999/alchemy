# -*- coding: utf-8 -*-
"""alchemy.core —— 炼金术化学内核（元素 / 几何 / 反应 / 目录 / 骨架分类）。

四个入口（推荐从顶层 ``alchemy`` 包使用）：

====================  ==========================================================
``simulate()``        大锅反应：原子序列 -> 产物分子（规则 1~11，可切 8/9 复现历史）
``embed()/validate()``六边形摆放与严格校验
``catalog``          84,225 条已验证物质的只读索引
``classify()``        骨架分类：6 级骨架块 / 38 库成员判定 / 三层拆解
====================  ==========================================================
"""
from . import canon, catalog, classify, elements, geometry, reactor

__all__ = ["canon", "catalog", "classify", "elements", "geometry", "reactor"]
