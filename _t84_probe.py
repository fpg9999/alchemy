import io, json, collections
from alchemy import attrs as A

recs = json.load(io.open("t4_catalog_all_validated.json", encoding="utf-8"))
cat = {r["formula"]: r for r in recs}

def n_skel(rec):
    k = len(A.skeleton_units(tuple(rec["atoms"]), [tuple(e) for e in rec["edges"]]))
    return max(1, k)

feeds = json.load(io.open("t62_loads.json", encoding="utf-8"))["batchA"]["rows"]
hist = collections.Counter()
tot = 0
ratios = []
for row in feeds:
    rec = cat.get(row["formula"])
    k = n_skel(rec)
    tot += row["count"]
    hist[k] += row["count"]
    ratios.append(len(rec["atoms"]) / k)
print("feed molecules:", tot)
print("n_skel histogram (by count):", dict(sorted(hist.items())))
print("mean skeletons/molecule:", round(sum(k * c for k, c in hist.items()) / tot, 3))
print("mean atoms/skeleton:", round(sum(ratios) / len(ratios), 2))
print("max k:", max(hist))

cnt = collections.Counter()
for rec in recs:
    cnt[n_skel(rec)] += 1
print("catalog n_skel distribution:", dict(sorted(cnt.items())))
