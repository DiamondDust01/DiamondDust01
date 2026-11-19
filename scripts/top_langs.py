#!/usr/bin/env python3
"""Gera SVGs (tema escuro e claro) com as linguagens mais usadas nos repositórios públicos."""
import json, os, sys, urllib.request
from html import escape

USER = os.environ.get("GH_USER", "DiamondDust01")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT_DIR", "assets")
TOP = 6
EXCLUDE = {"Jupyter Notebook"} if os.environ.get("EXCLUDE_NOTEBOOKS") else set()

COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "HTML": "#e34c26", "CSS": "#9b6bdc", "C": "#8a94a6", "C++": "#f34b7d",
    "C#": "#178600", "Java": "#b07219", "Jupyter Notebook": "#DA5B0B",
    "Shell": "#89e051", "PowerShell": "#2d79c7", "SCSS": "#c6538c",
}
FALLBACK = "#64748b"

THEMES = {
    "dark": dict(bg1="#111827", bg2="#15152d", stroke="#293548", title="#cbd5e1", text="#e2e8f0", muted="#94a3b8", track="#1e293b"),
    "light": dict(bg1="#ffffff", bg2="#f6f8fa", stroke="#d0d7de", title="#24292f", text="#24292f", muted="#57606a", track="#e5e9ee"),
}

def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}", headers={"Accept": "application/vnd.github+json", "User-Agent": "top-langs-svg"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def collect():
    totals, page = {}, 1
    while True:
        repos = api(f"/users/{USER}/repos?type=owner&per_page=100&page={page}")
        if not repos:
            break
        for repo in repos:
            if repo.get("fork") or repo.get("archived"):
                continue
            for lang, n in api(f"/repos/{USER}/{repo['name']}/languages").items():
                if lang not in EXCLUDE:
                    totals[lang] = totals.get(lang, 0) + n
        page += 1
    return totals

STRINGS = {
    "pt": dict(title="LINGUAGENS MAIS USADAS", other="Outras", alt="Linguagens mais usadas", desc="Proporção de bytes por linguagem nos repositórios públicos de {u}.", suffix=""),
    "en": dict(title="MOST USED LANGUAGES", other="Others", alt="Most used languages", desc="Share of bytes per language across the public repositories of {u}.", suffix="-en"),
}

def render(totals, t, L):
    items = sorted(totals.items(), key=lambda kv: -kv[1])
    top, rest = items[:TOP], sum(v for _, v in items[TOP:])
    if rest:
        top.append((L["other"], rest))
    total = sum(v for _, v in top) or 1
    W, bar_x, bar_w = 400, 24, 352
    rows = (len(top) + 1) // 2
    H = 86 + rows * 24 + 14
    segs, x = [], bar_x
    for i, (lang, v) in enumerate(top):
        w = bar_w * v / total
        segs.append((lang, x, w))
        x += w
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title description">',
           '  <title id="title">{L["alt"]}</title>',
           f'  <desc id="description">{L["desc"].format(u=escape(USER))}</desc>',
           f'  <defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t["bg1"]}"/><stop offset="1" stop-color="{t["bg2"]}"/></linearGradient>'
           f'<clipPath id="bar"><rect x="{bar_x}" y="58" width="{bar_w}" height="10" rx="5"/></clipPath></defs>',
           f'  <rect x="1" y="1" width="{W-2}" height="{H-2}" rx="14" fill="url(#bg)" stroke="{t["stroke"]}" stroke-width="2"/>',
           f'  <text x="24" y="38" fill="{t["title"]}" font-family="Segoe UI, Arial, sans-serif" font-size="14" font-weight="600" letter-spacing="1.5">{L["title"]}</text>',
           f'  <rect x="{bar_x}" y="58" width="{bar_w}" height="10" rx="5" fill="{t["track"]}"/>',
           '  <g clip-path="url(#bar)">']
    for lang, sx, w in segs:
        out.append(f'    <rect x="{sx:.2f}" y="58" width="{w:.2f}" height="10" fill="{COLORS.get(lang, FALLBACK)}"/>')
    out.append('  </g>')
    for i, (lang, v) in enumerate(top):
        cx = 24 + (i % 2) * 180
        cy = 94 + (i // 2) * 24 + 8
        pct = 100 * v / total
        out.append(f'  <circle cx="{cx+5}" cy="{cy-4}" r="5" fill="{COLORS.get(lang, FALLBACK)}"/>'
                   f'<text x="{cx+16}" y="{cy}" fill="{t["text"]}" font-family="Segoe UI, Arial, sans-serif" font-size="12">{escape(lang)} '
                   f'<tspan fill="{t["muted"]}">{pct:.1f}%</tspan></text>')
    out.append('</svg>\n')
    return "\n".join(out)

def main():
    totals = collect()
    if not totals:
        sys.exit("Nenhuma linguagem encontrada; abortando para não sobrescrever os SVGs.")
    os.makedirs(OUT, exist_ok=True)
    for L in STRINGS.values():
        for name, t in THEMES.items():
            with open(os.path.join(OUT, f"top-langs-{name}{L['suffix']}.svg"), "w", encoding="utf-8") as f:
                f.write(render(totals, t, L))
    print({k: v for k, v in sorted(totals.items(), key=lambda kv: -kv[1])[:TOP]})

if __name__ == "__main__":
    main()
