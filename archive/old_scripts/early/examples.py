# -*- coding: utf-8 -*-
import sys, json
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import hexmodel as H

MAXN = 11
shapes = H.enumerate_shapes(MAXN)
valid = []
for n in range(2, MAXN + 1):
    for s in shapes[n]:
        if H.valid_shape(s):
            valid.append(s)

from collections import Counter
print("valid shapes by n:", {n: sum(1 for s in valid if len(s) == n) for n in range(2, MAXN + 1)})
print("pure trivalent (0,0,n)?", any(H.signature(s)[0] == 0 and H.signature(s)[1] == 0 for s in valid))

want = [(2, 0, 0), (0, 3, 0), (1, 2, 1), (3, 0, 1), (0, 6, 0), (2, 1, 0), (0, 2, 2), (2, 2, 0), (0, 3, 2), (0, 4, 2), (1, 1, 3)]
for sig in want:
    cands = sorted([s for s in valid if H.signature(s) == sig], key=lambda s: (len(s), s))
    print(f"\n### signature {sig}  -> {len(cands)} shapes")
    for s in cands[:8]:
        print("   n=%d" % len(s), s)
