# -*- coding: utf-8 -*-
"""t12b_shards.py —— 生成 S 内全部无序对（含 A+A）的结果分片 + 汇总 jsonl。

每个 pair 记录为 [i, j, ridx]：
  i<=j 为 S 中的下标（t12b_S.json 顺序），ridx 指向 t12b_vec_data.json 的 "vecs"/"all" 数组。
  结果 = all[ridx]（ok, 产物列表），由总向量唯一决定。
分片：t12b_shards/pairs_XXXXX.jsonl，每片 10,000 对。
汇总：t12b_pairs.jsonl（全部对，同样的行格式）。
"""
import json
import os
import time

BASE = r"G:\AI work\deepseek\work1\alchemy"
SHARD_DIR = BASE + r"\t12b_shards"
SHARD_SIZE = 10000


def main():
    t0 = time.time()
    S = json.load(open(BASE + r"\t12b_S.json", encoding="utf-8"))
    vecs = [tuple(d["vec"]) for d in S]
    n = len(vecs)
    data = json.load(open(BASE + r"\t12b_results.json", encoding="utf-8"))
    uniq = [tuple(v) for v in data["vecs"]]
    ridx = {v: k for k, v in enumerate(uniq)}
    del data
    os.makedirs(SHARD_DIR, exist_ok=True)
    # 清理旧分片
    for f in os.listdir(SHARD_DIR):
        if f.endswith(".jsonl"):
            os.remove(os.path.join(SHARD_DIR, f))

    agg = open(BASE + r"\t12b_pairs.jsonl", "w", encoding="utf-8", buffering=1 << 20)
    shard = None
    shard_id = -1
    shard_cnt = 0
    npairs = 0
    for i in range(n):
        vi = vecs[i]
        lines = []
        for j in range(i, n):
            vj = vecs[j]
            v = (vi[0] + vj[0], vi[1] + vj[1], vi[2] + vj[2],
                 vi[3] + vj[3], vi[4] + vj[4], vi[5] + vj[5],
                 vi[6] + vj[6], vi[7] + vj[7], vi[8] + vj[8])
            lines.append("[%d,%d,%d]\n" % (i, j, ridx[v]))
        npairs += len(lines)
        for ln in lines:
            agg.write(ln)
        # 分片
        pos = 0
        while pos < len(lines):
            if shard is None or shard_cnt >= SHARD_SIZE:
                if shard is not None:
                    shard.close()
                shard_id += 1
                shard = open(os.path.join(SHARD_DIR, "pairs_%05d.jsonl" % shard_id),
                             "w", encoding="utf-8", buffering=1 << 20)
                shard_cnt = 0
            take = min(SHARD_SIZE - shard_cnt, len(lines) - pos)
            shard.writelines(lines[pos:pos + take])
            pos += take
            shard_cnt += take
        if (i + 1) % 500 == 0:
            print(f"  i={i+1}/{n} pairs={npairs} shards={shard_id+1} {time.time()-t0:.1f}s",
                  flush=True)
    if shard is not None:
        shard.close()
    agg.close()
    n_shards = shard_id + 1
    meta = {"n_pairs": npairs, "n_shards": n_shards, "shard_size": SHARD_SIZE,
            "n_uniq_vec": len(uniq), "sec": round(time.time() - t0, 1),
            "format": "[i,j,ridx] 每行一个；结果见 t12b_vec_data.json 的 all[ridx]"}
    json.dump(meta, open(BASE + r"\t12b_shards_meta.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    sz = sum(os.path.getsize(os.path.join(SHARD_DIR, f)) for f in os.listdir(SHARD_DIR))
    print(f"pairs={npairs} shards={n_shards} shard_size={sz/1e6:.1f}MB "
          f"agg={os.path.getsize(BASE + chr(92) + 't12b_pairs.jsonl')/1e6:.1f}MB "
          f"{time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
