# -*- coding: utf-8 -*-
"""pack_transfer_data.py：把超大原始数据压缩进 _data_gz/，生成清单（供 git 传输）"""
import gzip
import hashlib
import json
import os
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GZ = os.path.join(BASE, "_data_gz")
os.makedirs(GZ, exist_ok=True)

files = [
    "t12b_pairs.jsonl",
    "t4_catalog_all_validated.json",
    "t12b_vec_v3.json",
    "t12b_results.json",
    "t12c_sample_pairs.json",
    "t4_catalog_index.json",
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


manifest = []
for name in files:
    src = os.path.join(BASE, name)
    dst = os.path.join(GZ, name + ".gz")
    if not os.path.exists(src):
        print("skip missing", name)
        continue
    if not os.path.exists(dst):
        with open(src, "rb") as fi, gzip.open(dst, "wb", compresslevel=6) as fo:
            while True:
                b = fi.read(1024 * 1024)
                if not b:
                    break
                fo.write(b)
    manifest.append({
        "path": name,
        "gz": os.path.relpath(dst, BASE).replace("\\", "/"),
        "orig_bytes": os.path.getsize(src),
        "gz_bytes": os.path.getsize(dst),
        "orig_sha256": sha256(src),
        "gz_sha256": sha256(dst),
    })
    print("packed", name, os.path.getsize(src), "->", os.path.getsize(dst))

with open(os.path.join(GZ, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)
print("manifest entries", len(manifest))
