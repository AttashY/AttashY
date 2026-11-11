"""
Projects List generator.

Draws a terminal-style card for each of your projects: name with a
blinking cursor, description, main language, stars, when it was last
updated, and a donut chart of the languages inside the repo. Behind it,
soft colored "aurora" lights drift around.

Runs inside the same GitHub Action as the galaxy and writes
dist/projects.svg, which your README displays.
"""

import html
import json
import math
import os
import urllib.request
from datetime import datetime, timezone

from galaxy import USER, color_for, fetch_repos   # reuse code from galaxy.py

# ---------- settings you can play with ----------
FEATURED = []        # repo names to show, in order, e.g. ["jarvis", "portfolio"].
                     # Leave empty to show your most recently updated repos.
MAX_PROJECTS = 4     # how many cards (2 per row)
WIDTH = 800
CARD_W, CARD_H, GAP = 360, 128, 16
TOP = 72             # space for the header above the cards
RECENT_DAYS = 7      # repos updated within this many days get a green dot
# ------------------------------------------------


def get_json(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "projects-list"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as response:
        return json.load(response)


def pick_projects(repos):
    """Choose which repos get a card."""
    repos = [r for r in repos if r["name"].lower() != USER.lower()]  # skip the profile repo
    if FEATURED:
        by_name = {r["name"].lower(): r for r in repos}
        chosen = [by_name[n.lower()] for n in FEATURED if n.lower() in by_name]
    else:
        chosen = sorted(repos, key=lambda r: r["pushed_at"], reverse=True)
    return chosen[:MAX_PROJECTS]


def to_project(repo):
    """Keep just what a card needs. Also asks GitHub which languages are in the repo."""
    return {
        "name": repo["name"],
        "description": repo["description"],
        "stars": repo["stargazers_count"],
        "language": repo["language"],
        "languages": get_json(repo["languages_url"]),   # e.g. {"Python": 9120, "HTML": 340}
        "pushed_at": repo["pushed_at"],
    }


# ---------- small helpers ----------

def time_ago(timestamp, now):
    """'2026-11-08T12:00:00Z' -> '3d ago'"""
    then = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    seconds = (now - then).total_seconds()
    for unit, size in (("y", 31536000), ("mo", 2592000), ("d", 86400), ("h", 3600)):
        if seconds >= size:
            return f"{int(seconds // size)}{unit} ago"
    return "just now"


def wrap(text, width, max_lines):
    """Split text into lines of at most `width` characters, adding … if cut off."""
    words, lines, line = text.split(), [], ""
    for word in words:
        if len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 1].rstrip() + "…"
    return lines


def shorten(text, length):
    return text if len(text) <= length else text[: length - 1] + "…"


# ---------- drawing ----------

def donut(cx, cy, languages):
    """A ring chart of the repo's languages, biggest share labelled in the middle.

    Each slice is a circle outline where only part of the line is drawn.
    stroke-dasharray="slice gap" draws `slice` pixels, then skips the rest,
    and stroke-dashoffset slides it around to where the last slice ended.
    """
    r, thickness = 22, 7
    circumference = 2 * math.pi * r
    total = sum(languages.values())
    out = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#1f2747" stroke-width="{thickness}"/>']
    if not total:
        return out + [f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" class="pct">–</text>']
    done = 0.0
    for lang, size in sorted(languages.items(), key=lambda kv: kv[1], reverse=True):
        slice_len = size / total * circumference
        out.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color_for(lang)}" '
            f'stroke-width="{thickness}" stroke-dasharray="{slice_len:.2f} {circumference:.2f}" '
            f'stroke-dashoffset="{-done:.2f}" transform="rotate(-90 {cx} {cy})"/>')
        done += slice_len
    top = max(languages.values()) / total
    out.append(f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" class="pct">{round(top * 100)}%</text>')
    return out


def card(x, y, p, now):
    """One project card, with its top-left corner at (x, y)."""
    color = color_for(p["language"])
    pushed = datetime.fromisoformat(p["pushed_at"].replace("Z", "+00:00"))
    recent = (now - pushed).days < RECENT_DAYS
    desc = wrap(p["description"] or "No description provided.", 40, 2)
    out = [
        f'<g transform="translate({x} {y})">',
        f'<rect width="{CARD_W}" height="{CARD_H}" rx="10" class="card"/>',
        # header bar: small bullet, repo name, status dot
        f'<rect x="12" y="11" width="3" height="3" fill="#7aa2f7"/>',
        f'<text x="21" y="16" class="tab">{html.escape(shorten(p["name"], 40))}</text>',
        f'<circle cx="{CARD_W - 16}" cy="13" r="4" fill="{"#3fb950" if recent else "#565f89"}"'
        f'{" class=\"live\"" if recent else ""}/>',
        f'<line x1="0" y1="26" x2="{CARD_W}" y2="26" class="rule"/>',
        # title with a blinking cursor right after it
        f'<text x="14" y="50" class="name">{html.escape(shorten(p["name"], 24))}'
        f'<tspan class="cursor"> _</tspan></text>',
    ]
    for i, line in enumerate(desc):
        out.append(f'<text x="14" y="{68 + i * 14}" class="desc">{html.escape(line)}</text>')
    if p["language"]:
        pill_w = len(p["language"]) * 6.2 + 18
        out += [f'<rect x="14" y="94" width="{pill_w:.0f}" height="15" rx="7.5" class="pill"/>',
                f'<text x="{14 + pill_w / 2:.0f}" y="105" text-anchor="middle" class="pilltext">'
                f'{html.escape(p["language"])}</text>']
    out += [
        f'<text x="14" y="{CARD_H - 10}" class="meta"><tspan fill="{color}">★</tspan> '
        f'<tspan class="bright">{p["stars"]}</tspan></text>',
        f'<text x="{36 + 7 * len(str(p["stars"]))}" y="{CARD_H - 10}" class="meta">'
        f'updated {time_ago(p["pushed_at"], now)}</text>',
    ]
    out += donut(CARD_W - 52, 70, p["languages"])
    out.append("</g>")
    return out


def empty_card(y):
    """What shows before you have any public projects."""
    w = WIDTH - 64
    return [
        f'<g transform="translate(32 {y})">',
        f'<rect width="{w}" height="{CARD_H}" rx="10" class="card"/>',
        f'<rect x="12" y="11" width="3" height="3" fill="#7aa2f7"/>',
        f'<text x="21" y="16" class="tab">projects/</text>',
        f'<line x1="0" y1="26" x2="{w}" y2="26" class="rule"/>',
        f'<text x="14" y="58" class="desc"><tspan fill="#7aa2f7">$</tspan> ls projects/</text>',
        f'<text x="14" y="80" class="name">nothing here yet. first project loading'
        f'<tspan class="cursor"> _</tspan></text>',
        "</g>",
    ]


def aurora(height):
    """Big soft colored glows drifting slowly behind everything.

    Each glow is an oval filled with a radial gradient: full color in the
    middle, fading to see-through at the edge. animateTransform slides it
    along a little loop (the `values` list of x y moves).
    """
    blobs = [  # (x, y, width, height, color, seconds, drift path)
        (150, 40, 360, 220, "#4a5cff", 22, "0 0; 60 30; 20 -20; 0 0"),
        (620, 70, 420, 260, "#8a3ffc", 26, "0 0; -70 20; -20 40; 0 0"),
        (380, height - 30, 440, 200, "#14b8a6", 30, "0 0; 80 -20; -60 -10; 0 0"),
        (720, height - 50, 320, 220, "#e5484d", 24, "0 0; -40 -30; 10 -10; 0 0"),
    ]
    out = []
    for i, (x, y, w, h, color, seconds, path) in enumerate(blobs):
        out.append(
            f'<radialGradient id="glow{i}"><stop offset="0" stop-color="{color}" stop-opacity="0.32"/>'
            f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>')
        out.append(
            f'<g><animateTransform attributeName="transform" type="translate" values="{path}" '
            f'dur="{seconds}s" repeatCount="indefinite" calcMode="spline" '
            f'keySplines="0.45 0 0.55 1;0.45 0 0.55 1;0.45 0 0.55 1"/>'
            f'<ellipse cx="{x}" cy="{y}" rx="{w / 2}" ry="{h / 2}" fill="url(#glow{i})"/></g>')
    return out


def build_svg(projects, now=None):
    now = now or datetime.now(timezone.utc)
    rows = max(1, math.ceil(len(projects) / 2))
    height = TOP + rows * (CARD_H + GAP) + 14
    count = f"{len(projects)} project{'s' if len(projects) != 1 else ''}"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">',
        f"""<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0b1226"/><stop offset="1" stop-color="#060a16"/>
  </linearGradient>
  <clipPath id="frame"><rect width="{WIDTH}" height="{height}" rx="16"/></clipPath>
</defs>
<style>
  text {{ font-family: 'JetBrains Mono', Consolas, Menlo, 'DejaVu Sans Mono', 'Courier New', monospace; }}
  .eyebrow {{ font-size: 11px; letter-spacing: 3px; fill: #7aa2f7; font-weight: 600; }}
  .cmd {{ font-size: 11px; fill: #a9b1d6; }}
  .count {{ font-size: 11px; fill: #a9b1d6; }}
  .card {{ fill: #0b1020; fill-opacity: 0.78; stroke: #3d4785; }}
  .rule {{ stroke: #3d4785; }}
  .tab {{ font-size: 10px; fill: #c0caf5; }}
  .name {{ font-size: 15px; font-weight: 700; fill: #ffffff; }}
  .desc {{ font-size: 10.5px; fill: #a9b1d6; }}
  .pill {{ fill: #1f2a55; stroke: #3d4785; }}
  .pilltext {{ font-size: 9.5px; fill: #c0caf5; }}
  .meta {{ font-size: 10px; fill: #737aa2; }}
  .bright {{ fill: #c0caf5; font-weight: 700; }}
  .pct {{ font-size: 10px; font-weight: 700; fill: #ffffff; }}
  .foot {{ font-size: 9px; fill: #3b4261; font-family: 'Segoe UI', Helvetica, Arial, sans-serif; }}
  @keyframes blink {{ 0%, 49% {{ opacity: 1; }} 50%, 100% {{ opacity: 0; }} }}
  @keyframes live {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.35; }} }}
  .cursor {{ fill: #7aa2f7; animation: blink 1.1s step-end infinite; }}
  .live {{ animation: live 1.8s ease-in-out infinite; }}
</style>""",
        f'<g clip-path="url(#frame)">',
        f'<rect width="{WIDTH}" height="{height}" fill="url(#bg)"/>',
    ]
    parts += aurora(height)
    parts += [
        '</g>',
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="16" fill="none" stroke="#1f2a4d"/>',
        '<text x="32" y="36" class="eyebrow">PROJECTS.LIST</text>',
        '<text x="180" y="36" class="cmd">./projects.sh --all</text>',
        f'<text x="{WIDTH - 32}" y="36" text-anchor="end" class="count">{count}</text>',
        f'<line x1="32" y1="50" x2="{WIDTH - 32}" y2="50" class="rule"/>',
    ]
    if not projects:
        parts += empty_card(TOP)
    for i, p in enumerate(projects):
        x = 32 + (i % 2) * (CARD_W + GAP)
        y = TOP + (i // 2) * (CARD_H + GAP)
        parts += card(x, y, p, now)
    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    os.makedirs("dist", exist_ok=True)
    projects = [to_project(r) for r in pick_projects(fetch_repos())]
    with open("dist/projects.svg", "w", encoding="utf-8") as f:
        f.write(build_svg(projects))
    print(f"Wrote dist/projects.svg with {len(projects)} projects")
