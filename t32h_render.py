# -*- coding: utf-8 -*-
"""t32h_render.py：完整自然循环（反应→自分解→再反应）示例图 + 规律/玩法图"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from PIL import Image, ImageDraw
from t28_render import draw_mol, font, FONT, FONT_B

BASE = r"G:\AI work\deepseek\work1\alchemy"
examples = json.load(open(BASE + r"\t32_cycle_examples.json", encoding="utf-8"))
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
catf = {r["formula"] for r in cat}


def draw_state(d, box, state, title):
    x, y, w, h = box
    d.rounded_rectangle([x, y, x + w, y + h], radius=8, outline="#999", width=2)
    d.text((x + 8, y + 4), title, font=font(FONT_B, 14), fill="#111")
    n = len(state)
    cols = 2 if n <= 4 else 3
    rows = (n + cols - 1) // cols
    gw = (w - 16) // cols
    gh = (h - 30) // rows
    for i, mol in enumerate(state):
        r, c = divmod(i, cols)
        bx = x + 8 + c * gw
        by = y + 26 + r * gh
        draw_mol(d, mol, (bx, by, gw - 4, gh - 20))
        unstable = mol["formula"] not in catf
        color = "#c0392b" if unstable else "#333"
        d.text((bx + 3, by + gh - 20), mol["formula"], font=font(FONT_B, 11), fill=color)
        if unstable:
            d.text((bx + gw - 46, by + 2), "不稳定", font=font(FONT, 10), fill="#c0392b")


def main():
    W, H = 1760, 1500
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((24, 12), "自然环境的完整循环：不完全反应 → 不稳定中间体 → 半衰期自分解 → 再次反应",
           font=font(FONT_B, 27), fill="#111")
    d.text((24, 48), "红色 = 不稳定中间体（半衰期后按 M → F(v_M) 自分解）；绿色框 = 稳定碎片；灰色 = 旁观者（未参与）。",
           font=font(FONT, 14), fill="#555")
    row_h = 340
    for idx, e in enumerate(examples):
        y0 = 90 + idx * (row_h + 15)
        d.text((24, y0 + 4), f"示例 {e['name']}：", font=font(FONT_B, 18), fill="#111")
        d.text((24, y0 + 30), "初始：" + " + ".join(e["init"]), font=font(FONT, 13), fill="#555")
        states = e["states"]
        logs = e["log"]
        nstage = len(states)
        stage_w = (W - 48 - (nstage - 1) * 40) // nstage
        titles = []
        for i in range(nstage):
            if i == 0:
                titles.append("① 反应物")
            else:
                titles.append(f"第 {i} 步")
        for i, st in enumerate(states):
            bx = 24 + i * (stage_w + 40)
            draw_state(d, (bx, y0 + 56, stage_w, 250), st, titles[i])
            if i > 0:
                # 箭头与步骤说明
                ax = bx - 36
                d.line([ax, y0 + 170, ax + 26, y0 + 170], fill="#333", width=3)
                d.polygon([(ax + 22, y0 + 163), (ax + 22, y0 + 177), (ax + 34, y0 + 170)], fill="#333")
                label = "反应" if logs[i - 1]["type"] == "react" else "自分解"
                d.text((ax - 12, y0 + 185), label, font=font(FONT_B, 12), fill="#333")
        # 最终状态说明
        fin = states[-1]
        d.text((24, y0 + 308), "最终稳定态：" + "、".join(m["formula"] for m in fin),
               font=font(FONT_B, 13), fill="#1e8449")
    img.save(BASE + r"\images\t32_full_cycle.png")
    print("saved t32_full_cycle.png")

    # ---------------- 规律与玩法 ----------------
    W2, H2 = 1600, 980
    img2 = Image.new("RGB", (W2, H2), "white")
    d2 = ImageDraw.Draw(img2)
    d2.text((24, 12), "完整循环的规律与游戏化示例", font=font(FONT_B, 28), fill="#111")
    d2.text((24, 48), "600 次随机自然实验（p_react=0.30，q_decay=0.30，最多 80 步）",
            font=font(FONT, 14), fill="#555")

    d2.rounded_rectangle([24, 90, 760, 340], radius=10, fill="#f7fbff", outline="#7aa7d9", width=2)
    d2.text((40, 100), "统计规律", font=font(FONT_B, 20), fill="#123")
    lines = [
        "• 571/600 轨迹完全不反应（已稳定或键类不满足）",
        "• 26/600 只发生 1 轮反应，3/600 发生 2 轮反应，≥3 轮为 0",
        "• 链通常 1~2 轮后进入稳定固定点",
        "• 常见稳定碎片：XA、OP、PK、CF、CL、L2、OK、LF、C2",
        "• 常见自分解产物：OP(6)、PK(5)、XA(4)、OK/CF/CL(各 2)",
    ]
    y = 135
    for s in lines:
        d2.text((40, y), s, font=font(FONT, 15), fill="#222")
        y += 32

    d2.rounded_rectangle([790, 90, 1576, 340], radius=10, fill="#fff8f0", outline="#c98b3b", width=2)
    d2.text((806, 100), "节奏规律（半衰期 vs 反应概率）", font=font(FONT_B, 20), fill="#7a4a12")
    lines2 = [
        "• 半衰期长（q 小）→ 不稳定中间体积累，可被捕获/继续参与反应",
        "• 半衰期短（q 大）→ 中间体一闪而过，链很快收束为稳定物质",
        "• 反应概率高（p 大）→ 链式反应频繁，环境更\"沸腾\"",
        "• 反应概率低（p 小）→ 偶发反应，稳定态占主导",
        "• 两者竞争：p 高 + q 低 → 长链/复杂循环；p 低 + q 高 → 几乎静止",
    ]
    y = 140
    for s in lines2:
        d2.text((806, y), s, font=font(FONT, 15), fill="#3a2a12")
        y += 34

    d2.text((24, 380), "规律总结：", font=font(FONT_B, 20), fill="#111")
    laws = [
        "① 循环是\"开链\"：反应→不稳定→自分解→再反应，最终停在稳定物质；严格的闭环（回到原物质）在样本中未发现。",
        "② 碎片货币：自分解产物常是小分子（OP、PK、XA、CF、CL、L2、OK），它们会成为下一轮反应的原料；CF、CL、LF 等可被反复再生。",
        "③ 链式长度由\"反应遭遇率\"与\"半衰期\"共同决定：中间体活得越久，越可能被下一轮反应消耗；越短，越可能直接分解收束。",
        "④ 旁观者惰性：不含当前全局最不稳定类的分子全程不变，可以充当日后反应的\"催化剂/溶剂/见证者\"。",
        "⑤ 路径依赖：全局最不稳定类决定哪一对/哪一组分子先动，加入一个含更低距离键的分子会改变整条链。",
    ]
    y = 420
    for s in laws:
        d2.text((40, y), s, font=font(FONT, 15), fill="#222")
        y += 40

    d2.text((24, 640), "游戏化示例：", font=font(FONT_B, 20), fill="#111")
    games = [
        "1. 半衰期捕获：不稳定中间体只存在有限时间；玩家须在它自分解前采集/利用（稀有材料、限时事件）。",
        "2. 连锁爆米花：一次反应→自分解→二次反应，适合做连锁爆炸/连击特效与音效节奏。",
        "3. 碎片银行：OP/PK/XA/CF/CL/L2 等小碎片在多轮循环中重复出现，可设计\"碎片合成\"经济。",
        "4. 惰性催化剂：旁观者分子不参与但可稳定存在，天然适合做\"催化剂/容器/溶剂\"类道具。",
        "5. 反应节拍器：调整 q（半衰期）与 p（遭遇率）做成不同环境的\"节奏\"；极端参数可做\"死寂区/沸腾区\"。",
        "6. 隐藏闭环：真正的 A+B→…→A+B 闭环可作为隐藏机制（永动炼金阵/时间循环遗迹）。",
    ]
    y = 680
    for s in games:
        d2.text((40, y), s, font=font(FONT, 15), fill="#222")
        y += 36
    img2.save(BASE + r"\images\t32_cycle_rules.png")
    print("saved t32_cycle_rules.png")


if __name__ == "__main__":
    main()
