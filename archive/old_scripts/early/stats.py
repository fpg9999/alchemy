import sys, json
from collections import defaultdict
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import hexmodel as H

MAXN = 10
shapes = H.enumerate_shapes(MAXN)

print("=== 形状枚举（T 的连通诱导子图，度数<=3）===")
tot = 0
valid_by_n = {}
for n in range(2, MAXN + 1):
    all_sh = shapes[n]
    vsh = [s for s in all_sh if H.valid_shape(s)]
    valid_by_n[n] = vsh
    tot += len(vsh)
    print(f"n={n:2d}  诱导形状={len(all_sh):6d}  有效分子形状={len(vsh):5d}")

print(f"\n有效分子形状总数 (2..{MAXN}) = {tot}")

# 按价数签名归组
groups = defaultdict(list)
for n, vsh in valid_by_n.items():
    for s in vsh:
        groups[H.signature(s)].append((n, s))

print("\n=== 价数图案 (n1,n2,n3) -> 最小原子数 / 形状数 ===")
for sig in sorted(groups, key=lambda s: (sum(s), s)):
    items = groups[sig]
    mn = min(n for n, _ in items)
    print(f"  {sig}  最小 n={mn:2d}   shape数={len(items):4d}")

print("\n=== 是否存在纯三价 (0,0,n) 形状 ===")
pure3 = [sig for sig in groups if sig[0] == 0 and sig[1] == 0]
print("  纯三价签名:", pure3 if pure3 else "无（最大枚举到 n=%d）" % MAXN)
print("=== 纯二价 (0,n,0) 签名 ===")
print("  ", sorted([s for s in groups if s[0] == 0 and s[2] == 0]))
print("=== 纯一价 (n,0,0) 签名 ===")
print("  ", sorted([s for s in groups if s[1] == 0 and s[2] == 0]))

# 输出每个签名的最小形状，方便挑例子
print("\n=== 每个签名的最小形状（T 坐标） ===")
out = {}
for sig in sorted(groups, key=lambda s: (sum(s), s)):
    items = sorted(groups[sig], key=lambda t: t[0])
    mn = items[0][0]
    small = [s for n, s in items if n == mn]
    out[str(sig)] = {"min_n": mn, "count": len(items), "examples": [list(s) for s in small[:6]]}
    print(f"  {sig}: n={mn}, 最小形状数={len(small)}")

with open(r"G:\AI work\deepseek\work1\alchemy\enum_summary.json", "w", encoding="utf-8") as f:
    json.dump({"maxn": MAXN, "by_signature": out,
               "counts": {str(n): len(valid_by_n[n]) for n in valid_by_n}},
              f, ensure_ascii=False, indent=1)
print("\nwritten enum_summary.json")
