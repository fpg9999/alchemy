# -*- coding: utf-8 -*-
"""解压 _data_gz/manifest.json 中列出的大数据文件。"""
import gzip
import hashlib
import json
import os
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
GZ = os.path.join(BASE, "_data_gz")
MANIFEST = os.path.join(GZ, "manifest.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main():
    force = "--force" in sys.argv
    if not os.path.exists(MANIFEST):
        print("manifest not found:", MANIFEST)
        return 1
    rows = json.load(open(MANIFEST, encoding="utf-8"))
    for r in rows:
        src = os.path.join(BASE, r["gz"])
        dst = os.path.join(BASE, r["path"])
        if not os.path.exists(src):
            print("missing gz:", r["gz"])
            continue
        if os.path.exists(dst) and not force:
            if sha256(dst) == r["orig_sha256"]:
                print("ok (exists):", r["path"])
                continue
            print("exists but checksum differs; use --force to overwrite:", r["path"])
            continue
        os.makedirs(os.path.dirname(dst) or BASE, exist_ok=True)
        with gzip.open(src, "rb") as fi, open(dst, "wb") as fo:
            shutil.copyfileobj(fi, fo, 1024 * 1024)
        ok = sha256(dst) == r["orig_sha256"]
        print(("ok: " if ok else "CHECKSUM MISMATCH: ") + r["path"])
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
