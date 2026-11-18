# -*- coding: utf-8 -*-
"""t60_fill_report.py —— 用 t60_top20_data.json 填充 T60 总汇报模板里的表格"""
import json

BASE = r"G:\AI work\deepseek\work1\alchemy"


def elem_str(row):
    ec = row.get("element_counts") or {}
    return "".join("%s%s" % (e, (str(c) if c > 1 else ""))
                   for e, c in ec.items() if c)


def status(row):
    if row.get("in_29"):
        return "29聚素"
    if row.get("in_catalog"):
        return "目录内"
    return "目录外"


def top_table(rows):
    lines = ["| 排名 | 分子式 | 中文名 | 数量 | 原子数 | 元素组成 | 目录归属 |",
             "|---:|---|---|---:|---:|---|---|"]
    for r in rows:
        lines.append("| %d | `%s` | %s | %s | %d | %s | %s |" % (
            r["rank"], r["formula"], r["zh"], format(r["count"], ","),
            r["atoms"], elem_str(r), status(r)))
    return "\n".join(lines)


def important_table(rows):
    lines = ["| # | 分子式 | 中文名 | 原子数 | 出现实验（最佳排名→最大数量） | 出现次数 |",
             "|---:|---|---|---:|---|---:|"]
    for i, r in enumerate(rows, 1):
        occ = "；".join("%s#%s→%s" % (o["experiment"], o["rank"], format(o["count"], ","))
                        for o in r["occurrences"])
        lines.append("| %d | `%s` | %s | %d | %s | %d |" % (
            i, r["formula"], r["zh"], r["atoms"], occ, r["n_experiments"]))
    return "\n".join(lines)


def main():
    data = json.load(open(BASE + r"\t60_top20_data.json", encoding="utf-8"))
    tpl = open(BASE + r"\docs\templates\t60_report_template.md", encoding="utf-8").read()
    by = {e["name"]: e for e in data["experiments"]}
    for key, name in (("T55_TABLE", "T55"), ("T56_TABLE", "T56"),
                      ("T57_TABLE", "T57"), ("T58_TABLE", "T58"),
                      ("T59A_TABLE", "T59A"), ("T59B_TABLE", "T59B"),
                      ("T59A_HF_TABLE", "T59A_hf"), ("T59B_HF_TABLE", "T59B_hf")):
        tpl = tpl.replace("{{%s}}" % key, top_table(by[name]["top20"]))
    tpl = tpl.replace("{{IMPORTANT_TABLE}}", important_table(data["important"]))
    out = BASE + r"\docs\T60_SERIES_SUMMARY.md"
    open(out, "w", encoding="utf-8").write(tpl)
    print("wrote", out, "chars", len(tpl))


if __name__ == "__main__":
    main()
