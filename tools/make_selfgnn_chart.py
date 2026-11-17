"""SelfGNNplus results chart (dark + light SVG) from the published comparison table.

Source: assets/data/selfgnnplus_compare.csv (copy of SelfGNNplus/utils/compare_data.csv).
Two panels (HR@10, NDCG@10); per dataset: SelfGNNplus, SelfGNN, best other baseline.
usage: python tools/make_selfgnn_chart.py
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = {r["Data"]: r for r in csv.DictReader(open(ROOT / "assets/data/selfgnnplus_compare.csv"))}
DATASETS = ["Amazon", "Gowalla", "MovieLens", "Yelp"]
METRICS = [("Top 10 HR", "Hit Rate@10"), ("Top 10 NDCG", "NDCG@10")]
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

THEMES = {
    "dark": dict(bg="#0d1117", edge="#30363d", fg="#f0f6fc", sub="#c9d1d9", mute="#8b949e", grid="#21262d",
                 bars=["#76b900", "#8b949e", "#484f58"]),
    "light": dict(bg="#ffffff", edge="#d0d7de", fg="#1f2328", sub="#424a53", mute="#57606a", grid="#eaeef2",
                  bars=["#5a8f00", "#6e7781", "#afb8c1"]),
}


def series(key, ds):
    k = f"{ds} {key}"
    plus, base = float(rows["SelfGNNplus"][k]), float(rows["SelfGNN"][k])
    other = max((float(r[k]), n) for n, r in rows.items() if n not in ("SelfGNNplus", "SelfGNN"))
    return [(plus, "SelfGNNplus"), (base, "SelfGNN"), other]


def bar(x, y0, w, h, r=4):
    """Vertical bar anchored to the baseline, 4px rounded top."""
    r = min(r, h / 2, w / 2)
    return (f"M{x:.1f} {y0:.1f} V{y0 - h + r:.1f} Q{x:.1f} {y0 - h:.1f} {x + r:.1f} {y0 - h:.1f} "
            f"H{x + w - r:.1f} Q{x + w:.1f} {y0 - h:.1f} {x + w:.1f} {y0 - h + r:.1f} V{y0:.1f} Z")


def chart(theme):
    t = THEMES[theme]
    W, H = 1200, 470
    el = [f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16" fill="{t["bg"]}" stroke="{t["edge"]}"/>',
          f'<text x="40" y="52" font-family="{SANS}" font-size="24" font-weight="700" fill="{t["fg"]}">SelfGNNplus vs. 19 baselines</text>',
          f'<text x="40" y="80" font-family="{SANS}" font-size="15" fill="{t["mute"]}">Top-10 recommendation, 4 benchmark datasets · higher is better · +% = gain over SelfGNN</text>']
    # legend (top right)
    lx = 690
    for (name, col) in zip(["SelfGNNplus", "SelfGNN", "Best other baseline"], t["bars"]):
        el.append(f'<rect x="{lx}" y="40" width="12" height="12" rx="3" fill="{col}"/>')
        el.append(f'<text x="{lx + 18}" y="51" font-family="{SANS}" font-size="14" fill="{t["sub"]}">{name}</text>')
        lx += 18 + 9 * len(name) + 28
    panel_w, top, base_y = 540, 130, 410
    for p, (key, label) in enumerate(METRICS):
        x0 = 40 + p * (panel_w + 40)
        vals = [series(key, ds) for ds in DATASETS]
        vmax = 0.8 if key.endswith("HR") else 0.5
        step = 0.2 if key.endswith("HR") else 0.1
        sc = (base_y - top) / vmax
        el.append(f'<text x="{x0}" y="{top - 16}" font-family="{SANS}" font-size="16" font-weight="600" fill="{t["fg"]}">{label}</text>')
        v = 0.0
        while v <= vmax + 1e-9:
            y = base_y - v * sc
            el.append(f'<line x1="{x0 + 34}" x2="{x0 + panel_w}" y1="{y:.1f}" y2="{y:.1f}" stroke="{t["grid"]}" stroke-width="1"/>')
            el.append(f'<text x="{x0 + 26}" y="{y + 4:.1f}" text-anchor="end" font-family="{SANS}" font-size="12" fill="{t["mute"]}">{v:.1f}</text>')
            v += step
        gw = (panel_w - 40) / len(DATASETS)
        bw = 32
        for d, (ds, trio) in enumerate(zip(DATASETS, vals)):
            gx = x0 + 40 + d * gw + (gw - 3 * bw - 4) / 2
            for b, ((val, name), col) in enumerate(zip(trio, t["bars"])):
                bx = gx + b * (bw + 2)          # 2px surface gap between bars
                h = val * sc
                el.append(f'<path d="{bar(bx, base_y, bw, h)}" fill="{col}"><title>{ds} · {name}: {val:.3f}</title></path>')
                el.append(f'<text x="{bx + bw / 2:.1f}" y="{base_y - h - 6:.1f}" text-anchor="middle" font-family="{SANS}" '
                          f'font-size="11" fill="{t["fg"] if b == 0 else t["mute"]}">{val:.3f}</text>')
            gain = 100 * (trio[0][0] / trio[1][0] - 1)
            el.append(f'<text x="{gx + 1.5 * bw + 2:.1f}" y="{base_y + 24}" text-anchor="middle" font-family="{SANS}" font-size="14" fill="{t["sub"]}">{ds}</text>')
            el.append(f'<text x="{gx + 1.5 * bw + 2:.1f}" y="{base_y + 44}" text-anchor="middle" font-family="{SANS}" font-size="13" font-weight="700" fill="{t["fg"]}">+{gain:.1f}%</text>')
        el.append(f'<line x1="{x0 + 34}" x2="{x0 + panel_w}" y1="{base_y}" y2="{base_y}" stroke="{t["mute"]}" stroke-width="1"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H + 10}" width="{W}" height="{H + 10}" role="img" '
           f'aria-label="SelfGNNplus beats SelfGNN and 18 other baselines on HR@10 and NDCG@10 on Amazon, Gowalla, MovieLens and Yelp">\n'
           + "\n".join(el).replace(f'height="{H - 2}"', f'height="{H + 8}"') + "\n</svg>\n")
    out = ROOT / f"assets/selfgnnplus-results-{theme}.svg"
    out.write_text(svg)
    print(out.relative_to(ROOT))


for th in THEMES:
    chart(th)
