# -*- coding: utf-8 -*-
"""make_transfer_archive.py：生成全量 zip（含原始大文件与 _data_gz）"""
import hashlib
import os
import zipfile

BASE = r"G:\AI work\deepseek\work1\alchemy"
OUT = r"G:\AI work\deepseek\work1\alchemy_transfer_2026-11-14.zip"
EXCLUDE_DIRS = {".git", "__pycache__", "_compression_test"}
EXCLUDE_FILES = set()


def main():
    count = 0
    total = 0
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(BASE):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fn in files:
                if fn in EXCLUDE_FILES:
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, BASE).replace("\\", "/")
                arc = "alchemy/" + rel
                zf.write(full, arc)
                count += 1
                total += os.path.getsize(full)
    h = hashlib.sha256()
    with open(OUT, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    print("zip:", OUT)
    print("files:", count, "raw MB:", round(total / 1e6, 1),
          "zip MB:", round(os.path.getsize(OUT) / 1e6, 1))
    print("sha256:", h.hexdigest())


if __name__ == "__main__":
    main()
