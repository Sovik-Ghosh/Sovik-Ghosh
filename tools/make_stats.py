"""GitHub stats card (dark + light SVG), public AND private repos, aggregated.

Privacy: the card contains only totals, a per-day commit calendar and language
shares. No repository name, description or commit message is written to the
SVG or printed to stdout (Action logs of a public repo are public).
Auth: STATS_TOKEN (read-only PAT that can see private repos) if set, otherwise
the logged-in `gh` CLI. GITHUB_TOKEN is not enough: it cannot read other private repos.
usage: python tools/make_stats.py
"""
import json
import os
import subprocess
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from frost import background, glass

ROOT = Path(__file__).resolve().parent.parent
SKIP_LANGS = {"Jupyter Notebook"}   # notebook bytes are mostly outputs
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace"


def gql(query, **variables):
    token = os.environ.get("STATS_TOKEN")
    if token:
        req = urllib.request.Request("https://api.github.com/graphql",
                                     data=json.dumps({"query": query, "variables": variables}).encode(),
                                     headers={"Authorization": f"Bearer {token}", "User-Agent": "profile-stats"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                res = json.load(r)
        except Exception:
            raise SystemExit("GitHub API request failed (details suppressed)") from None
    else:
        args = ["gh", "api", "graphql", "-f", f"query={query}"]
        for k, v in variables.items():
            args += ["-F" if isinstance(v, int) else "-f", f"{k}={v}"]
        for attempt in range(3):
            proc = subprocess.run(args, capture_output=True, text=True)
            if proc.returncode == 0:
                break
        else:
            raise SystemExit("gh api graphql failed (details suppressed to avoid leaking repo ids)")
        res = json.loads(proc.stdout)
    if res.get("errors"):
        raise SystemExit("GraphQL error (details suppressed to avoid leaking repo names)")
    return res["data"]


now = datetime.now(timezone.utc)
today = now.date()
since = (today - timedelta(days=364 + (today.weekday() + 1) % 7)).isoformat() + "T00:00:00Z"  # start on a Sunday

v = gql("""query { viewer { id login followers { totalCount }
  repositories(ownerAffiliations: OWNER, isFork: false, first: 100) { totalCount nodes {
    id isPrivate stargazerCount
    languages(first: 20, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } } } } } }""")["viewer"]
uid, login = v["id"], v["login"]
repos = v["repositories"]["nodes"]

HIST = """query($repo: ID!, $uid: ID!, $since: GitTimestamp!, $after: String) { node(id: $repo) { ... on Repository {
  defaultBranchRef { target { ... on Commit { history(first: 100, after: $after, since: $since, author: {id: $uid}) {
    pageInfo { hasNextPage endCursor } nodes { committedDate } } } } } } } }"""
per_day, per_month, active = Counter(), Counter(), 0
for r in repos:
    after, seen = None, False
    while True:
        kw = dict(repo=r["id"], uid=uid, since=since)
        if after:
            kw["after"] = after
        ref = gql(HIST, **kw)["node"]["defaultBranchRef"]
        if not ref:
            break
        h = ref["target"]["history"]
        for c in h["nodes"]:
            per_day[c["committedDate"][:10]] += 1
            per_month[(c["committedDate"][:7], "c")] += 1
            seen = True
        if not h["pageInfo"]["hasNextPage"]:
            break
        after = h["pageInfo"]["endCursor"]
    active += seen

pr_nodes = gql("""query($q: String!) { search(query: $q, type: ISSUE, first: 100) {
  nodes { ... on PullRequest { createdAt } } } }""", q=f"author:{login} is:pr created:>={since[:10]}")["search"]["nodes"]
for n in pr_nodes:
    if n:
        per_month[(n["createdAt"][:7], "p")] += 1

prs = gql("query($q: String!) { search(query: $q, type: ISSUE, first: 1) { issueCount } }",
          q=f"author:{login} is:pr")["search"]["issueCount"]

# per-day series for the streaks
start = date.fromisoformat(since[:10])
days = [{"date": (start + timedelta(d)).isoformat(),
         "contributionCount": per_day.get((start + timedelta(d)).isoformat(), 0)}
        for d in range((today - start).days + 1)]

longest = run = 0
for d in days:
    run = run + 1 if d["contributionCount"] else 0
    longest = max(longest, run)
current = 0
for i, d in enumerate(reversed(days)):
    if d["contributionCount"]:
        current += 1
    elif i:
        break

langs = {}
for r in repos:
    for e in r["languages"]["edges"]:
        n = e["node"]["name"]
        if n not in SKIP_LANGS:
            langs.setdefault(n, [0, e["node"]["color"] or "#8b949e"])[0] += e["size"]
top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:6]
total = sum(b for b, _ in langs.values()) or 1


n_priv = sum(r["isPrivate"] for r in repos)
kpis = [
    (f"{sum(per_day.values()):,}", "commits", "past year · all repos"),
    (f"{active}", "active repos", "committed to · past year"),
    (f"{current}", "day streak", f"current · longest {longest}"),
    (f"{prs}", "pull requests", "all time"),
    (f"{len(repos)}", "repositories", f"{len(repos) - n_priv} public · {n_priv} private"),
    (f"{sum(r['stargazerCount'] for r in repos)}", "stars", f"{v['followers']['totalCount']} followers"),
]

THEMES = {
    "dark": dict(bg0="#0d1117", bg1="#161b22", edge="#30363d", fg="#f0f6fc", sub="#c9d1d9", mute="#8b949e",
                 tile="#161b22", green="#76b900", grid="#21262d", pr="#3987e5", com="#76b900"),
    "light": dict(bg0="#ffffff", bg1="#f6f8fa", edge="#d0d7de", fg="#1f2328", sub="#424a53", mute="#57606a",
                  tile="#f6f8fa", green="#5a8f00", grid="#eaeef2", pr="#2a78d6", com="#5a8f00"),
}


# last 12 calendar months, oldest first
months = []
y, m = today.year, today.month
for _ in range(12):
    months.append(f"{y:04d}-{m:02d}")
    y, m = (y, m - 1) if m > 1 else (y - 1, 12)
months.reverse()


def card(theme):
    t = THEMES[theme]
    W, H = 1200, 330
    el = [background(W, H, theme, [(150, 40, 220), (1050, 300, 260), (650, 160, 200)]),
          glass(20, 136, 772, 180, theme, rx=14), glass(804, 136, 376, 180, theme, rx=14)]
    # KPI tiles
    tw, gap, x, y = 183, 12, 20, 28    # 6 tiles span x 20..1180, same as the panels
    for val, label, note in kpis:
        el.append(glass(x, y, tw, 92, theme))
        el.append(f'<text x="{x + 16}" y="{y + 44}" font-family="{SANS}" font-size="30" font-weight="800" fill="{t["fg"]}">{val}</text>')
        el.append(f'<text x="{x + 16}" y="{y + 66}" font-family="{SANS}" font-size="14" fill="{t["sub"]}">{label}</text>')
        if note:
            el.append(f'<text x="{x + 16}" y="{y + 82}" font-family="{SANS}" font-size="11" fill="{t["mute"]}">{note}</text>')
        x += tw + gap
    # grouped bars: commits and pull requests per month (all repos)
    cx0, cy_top, cy_base, cw = 32, 186, 286, 740
    el.append(f'<text x="{cx0}" y="{cy_top - 30}" font-family="{SANS}" font-size="15" font-weight="600" fill="{t["fg"]}">Activity per month · all repos</text>')
    lgx = cx0 + cw
    for name, col in (("pull requests", t["pr"]), ("commits", t["com"])):
        lgx -= 9 * len(name) + 30
        el.append(f'<rect x="{lgx}" y="{cy_top - 41}" width="12" height="12" rx="3" fill="{col}"/>')
        el.append(f'<text x="{lgx + 18}" y="{cy_top - 30}" font-family="{SANS}" font-size="13" fill="{t["sub"]}">{name}</text>')
    vals = [(per_month[(mo, "c")], per_month[(mo, "p")]) for mo in months]
    vmax = max([1] + [max(p) for p in vals])
    nice = next(n for n in (2, 4, 5, 10, 20, 25, 40, 50, 80, 100, 200, 500, 1000, 10**9) if n >= vmax)
    for frac in (0, 0.5, 1):
        gy = cy_base - frac * (cy_base - cy_top)
        el.append(f'<line x1="{cx0 + 28}" x2="{cx0 + cw}" y1="{gy:.1f}" y2="{gy:.1f}" stroke="{t["grid"] if frac else t["mute"]}" stroke-width="1"/>')
        el.append(f'<text x="{cx0 + 20}" y="{gy + 4:.1f}" text-anchor="end" font-family="{SANS}" font-size="11" fill="{t["mute"]}">{nice * frac:g}</text>')
    gw = (cw - 36) / len(months)
    bw = min(18, (gw - 14) / 2)
    for i, (mo, (com, pr)) in enumerate(zip(months, vals)):
        gx = cx0 + 36 + i * gw + (gw - 2 * bw - 2) / 2
        for j, (val, col, kind) in enumerate(((com, t["com"], "commits"), (pr, t["pr"], "pull requests"))):
            bx = gx + j * (bw + 2)                     # 2px surface gap
            h = (cy_base - cy_top) * val / nice
            if val:
                r = min(4, h / 2, bw / 2)
                el.append(f'<path d="M{bx:.1f} {cy_base} V{cy_base - h + r:.1f} Q{bx:.1f} {cy_base - h:.1f} {bx + r:.1f} {cy_base - h:.1f} '
                          f'H{bx + bw - r:.1f} Q{bx + bw:.1f} {cy_base - h:.1f} {bx + bw:.1f} {cy_base - h + r:.1f} V{cy_base} Z" fill="{col}">'
                          f'<title>{mo} · {kind}: {val}</title></path>')
                el.append(f'<text x="{bx + bw / 2:.1f}" y="{cy_base - h - 5:.1f}" text-anchor="middle" font-family="{SANS}" font-size="10" fill="{t["mute"]}">{val}</text>')
        label = date.fromisoformat(mo + "-01").strftime("%b")
        el.append(f'<text x="{gx + bw + 1:.1f}" y="{cy_base + 18}" text-anchor="middle" font-family="{SANS}" font-size="11" fill="{t["mute"]}">{label}</text>')
    # languages
    lx0, ly0, lw = 820, 172, 348
    el.append(f'<text x="{lx0}" y="{ly0 - 14}" font-family="{SANS}" font-size="15" font-weight="600" fill="{t["fg"]}">Top languages</text>')
    el.append(f'<text x="{lx0 + lw}" y="{ly0 - 14}" text-anchor="end" font-family="{SANS}" font-size="11" fill="{t["mute"]}">all repos · by code size</text>')
    bx = lx0
    for i, (n, (b, col)) in enumerate(top):
        w = lw * b / total - (2 if i < len(top) - 1 else 0)   # 2px surface gap
        el.append(f'<rect x="{bx:.1f}" y="{ly0}" width="{max(w, 1):.1f}" height="10" rx="3" fill="{col}"/>')
        bx += lw * b / total
    for i, (n, (b, col)) in enumerate(top):
        cx, cy = lx0 + (i % 2) * (lw / 2), ly0 + 40 + (i // 2) * 30
        el.append(f'<circle cx="{cx + 6}" cy="{cy - 4}" r="5" fill="{col}"/>')
        el.append(f'<text x="{cx + 18}" y="{cy}" font-family="{SANS}" font-size="14" fill="{t["sub"]}">{n}</text>')
        el.append(f'<text x="{cx + lw / 2 - 16}" y="{cy}" text-anchor="end" font-family="{MONO}" font-size="13" fill="{t["mute"]}">{100 * b / total:.1f}%</text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           f'aria-label="GitHub stats for {login}">\n' + "\n".join(el) + "\n</svg>\n")
    out = ROOT / f"assets/stats-{theme}.svg"
    if not out.exists() or out.read_text() != svg:
        out.write_text(svg)
        print("updated", out.name)


for th in THEMES:
    card(th)
