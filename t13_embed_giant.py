# -*- coding: utf-8 -*-
"""T13 embed giant：对 lead 提供的 258 / 346 原子巨型图做 pot_v2 严格摆放校验（预算 5e7）。

结构来自 t13_scale3.json / t13_scale4.json（lead 产出，list of {formula, atoms, edges}）。
结果写 t13_embed_giant.json。
用法：python t13_embed_giant.py [--budget 50000000]
"""
import sys, os, json, time, argparse

HERE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, HERE)
import pot_v2

FILES = [("scale3", "t13_scale3.json"), ("scale4", "t13_scale4.json")]
OUT = os.path.join(HERE, "t13_embed_giant.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=50_000_000)
    ap.add_argument("--tag", default=None, help="scale3 / scale4；缺省两者顺序跑")
    args = ap.parse_args()
    files = [f for f in FILES if args.tag is None or f[0] == args.tag]
    single_out = os.path.join(HERE, f"t13_embed_giant_{args.tag}.json")
    out_path = single_out if args.tag else OUT
    rows = []
    for tag, fn in files:
        p = os.path.join(HERE, fn)
        d = json.load(open(p, encoding="utf-8"))
        m = max(d, key=lambda x: len(x["atoms"]))
        atoms, edges = m["atoms"], [tuple(e) for e in m["edges"]]
        print(f"[giant] {tag}: n={len(atoms)} formula={m['formula']} "
              f"bonds={len(edges)} budget={args.budget}", flush=True)
        t0 = time.time()
        place = pot_v2.embed_mol2(atoms, edges, max_nodes=args.budget)
        t_embed = time.time() - t0
        ok, msg = pot_v2.validate_place(place, atoms, edges)
        row = {"tag": tag, "n": len(atoms), "formula": m["formula"],
               "budget": args.budget, "status": "ok" if (place and ok) else "fail",
               "valid": bool(ok), "msg": msg, "t_embed": round(t_embed, 1)}
        if place and ok:
            row["place"] = {str(k): list(v) for k, v in place.items()}
        rows.append(row)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print(f"[giant] {tag}: status={row['status']} valid={row['valid']} "
              f"t={t_embed:.1f}s msg={msg[:60]}", flush=True)


if __name__ == "__main__":
    main()
