# -*- coding: utf-8 -*-
"""t54_update_gz.py：目录结构替换后，更新 _data_gz 的压缩副本与 manifest SHA。"""
import gzip
import hashlib
import json
import os
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
BASE = r"G:\AI work\deepseek\work1\alchemy"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    orig = BASE + r"\t4_catalog_all_validated.json"
    gz_path = BASE + r"\_data_gz\t4_catalog_all_validated.json.gz"
    man_path = BASE + r"\_data_gz\manifest.json"
    with open(orig, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
        while True:
            chunk = f_in.read(1 << 20)
            if not chunk:
                break
            f_out.write(chunk)
    manifest = json.load(open(man_path, encoding="utf-8"))
    for e in manifest:
        if e["path"] == "t4_catalog_all_validated.json":
            e["orig_bytes"] = os.path.getsize(orig)
            e["gz_bytes"] = os.path.getsize(gz_path)
            e["orig_sha256"] = sha256_file(orig)
            e["gz_sha256"] = sha256_file(gz_path)
            print(json.dumps(e, ensure_ascii=False, indent=1))
            break
    json.dump(manifest, open(man_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("manifest updated")


if __name__ == "__main__":
    main()
