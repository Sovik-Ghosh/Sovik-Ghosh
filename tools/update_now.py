"""Rewrite the README block (recent public releases and pushes only) between <!-- NOW:START --> and <!-- NOW:END -->.

Uses only public GitHub REST endpoints. Set GITHUB_TOKEN to raise the rate limit.
usage: python tools/update_now.py [README.md]
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

USER = "Sovik-Ghosh"
SKIP = {USER}                     # the profile repo itself
RECENT = timedelta(days=90)       # only show activity newer than this
README = sys.argv[1] if len(sys.argv) > 1 else "README.md"


def get(path):
    req = urllib.request.Request(f"https://api.github.com{path}",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-readme-updater"})
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def day(ts):
    return ts[:10]


now = datetime.now(timezone.utc)


def recent(ts):
    return now - datetime.fromisoformat(ts.replace("Z", "+00:00")) < RECENT


repos = [r for r in get(f"/users/{USER}/repos?per_page=100&sort=pushed") or []
         if not r["fork"] and not r["archived"] and r["name"] not in SKIP]

lines = []
releases = []
for r in repos[:10]:
    rel = get(f"/repos/{USER}/{r['name']}/releases/latest")
    if rel and recent(rel["published_at"]):
        releases.append((rel["published_at"], r["name"], rel["tag_name"], rel["html_url"]))
if releases:
    ts, name, tag, url = max(releases)
    lines.append(f"- 🏷️ **Latest release:** [{name} {tag}]({url}) · {day(ts)}")

for r in [r for r in repos if recent(r["pushed_at"])][:3]:
    desc = (r["description"] or "").split(". ")[0].strip()
    desc = (desc[:90] + "…") if len(desc) > 90 else desc
    lines.append(f"- 🔨 [**{r['name']}**]({r['html_url']}) · last push {day(r['pushed_at'])}" + (f" — {desc}" if desc else ""))

block = ("\n".join(lines) + "\n\n") if lines else ""
block += "<sub>Recent public releases and pushes appear here automatically.</sub>"

text = open(README, encoding="utf-8").read()
new = re.sub(r"(<!-- NOW:START -->).*?(<!-- NOW:END -->)", lambda m: m.group(1) + "\n" + block + "\n" + m.group(2), text, flags=re.S)
if new != text:
    open(README, "w", encoding="utf-8").write(new)
    print("README updated")
else:
    print("no change")
