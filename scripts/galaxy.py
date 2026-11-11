"""
Repo Galaxy generator.

Draws an animated spiral galaxy as an SVG image. Every public repo you own
becomes a bright star on one of the spiral arms, sized by how many GitHub
stars it has and colored by its main language.

Runs inside a GitHub Action (see .github/workflows/galaxy.yml) and writes
dist/galaxy.svg, which your README displays.
"""

import html
import json
import math
import os
import random
import urllib.request
from datetime import date

# ---------- settings you can play with ----------
USER = os.environ.get("GITHUB_USER", "AttashY")
WIDTH, HEIGHT = 800, 380          # size of the whole card
CX, CY = 545, 195                 # where the galaxy's center sits
ARMS = 2                          # number of spiral arms
DUST_PER_ARM = 260                # background "dust" stars per arm
TILT = 0.55                       # 1 = seen from above, smaller = more tilted
LANG_COLORS = {                   # star color for each language
    "Python": "#7aa2f7", "JavaScript": "#e0af68", "TypeScript": "#2ac3de",
    "HTML": "#f7768e", "CSS": "#bb9af7", "Java": "#ff9e64",
    "C++": "#9ece6a", "C": "#73daca", "Jupyter Notebook": "#ff9e64",
}
DEFAULT_COLOR = "#c0caf5"
# ------------------------------------------------


def fetch_repos():
    """Ask the GitHub API for this user's public repos (skipping forks)."""
    url = f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "repo-galaxy",
    })
    token = os.environ.get("GITHUB_TOKEN")
    if token:  # the token just raises the API's rate limit
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as response:
        repos = json.load(response)
    return [r for r in repos if not r["fork"]]


def spiral_point(arm, theta):
    """Position on a logarithmic spiral: radius grows as the angle grows."""
    radius = 12 * math.exp(0.3 * theta)
    angle = theta + arm * (2 * math.pi / ARMS)
    x = CX + radius * math.cos(angle)
    y = CY + radius * math.sin(angle) * TILT
    return x, y, radius


def dust_stars(rng):
    """Small faint stars scattered along the arms, plus a few random ones."""
    out = []
    for arm in range(ARMS):
        for _ in range(DUST_PER_ARM):
            theta = rng.uniform(1.0, 3 * math.pi)
            x, y, radius = spiral_point(arm, theta)
            spread = 1.5 + radius * 0.06          # arms get fuzzier further out
            x += rng.gauss(0, spread)
            y += rng.gauss(0, spread * TILT)
            size = rng.uniform(0.5, 1.5)
            opacity = rng.uniform(0.25, 0.85)
            twinkle = f' class="t{rng.randint(1, 3)}"' if rng.random() < 0.25 else ""
            color = rng.choice(["#a9b8ff", "#c0caf5", "#8fa1e8", "#d4c4ff"])
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size:.2f}" '
                       f'fill="{color}" opacity="{opacity:.2f}"{twinkle}/>')
    for _ in range(90):                          # loose stars across the card
        x, y = rng.uniform(260, WIDTH - 10), rng.uniform(10, HEIGHT - 10)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rng.uniform(0.3, 0.9):.2f}" '
                   f'fill="#c0caf5" opacity="{rng.uniform(0.1, 0.4):.2f}"/>')
    return out


def repo_stars(repos):
    """One glowing star per repo, placed along the arms, biggest first."""
    out = []
    repos = sorted(repos, key=lambda r: r["stargazers_count"], reverse=True)
    for i, repo in enumerate(repos):
        arm = i % ARMS
        theta = min(4.2 + (i // ARMS) * 1.6, 3 * math.pi - 0.2)
        x, y, _ = spiral_point(arm, theta)
        size = min(3 + 2.2 * math.sqrt(repo["stargazers_count"]), 12)
        color = LANG_COLORS.get(repo["language"], DEFAULT_COLOR)
        name = html.escape(repo["name"])
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size * 2.6:.1f}" '
                   f'fill="{color}" opacity="0.18" filter="url(#blur)"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size:.1f}" fill="{color}" class="pulse"/>')
        if i < 8:  # label the top 8 so it doesn't get cluttered
            out.append(f'<text x="{x + size + 5:.1f}" y="{y + 3:.1f}" class="label">{name}</text>')
    return out


def legend(repos):
    """Left-side panel: title, totals and a language color key."""
    total_stars = sum(r["stargazers_count"] for r in repos)
    lines = [
        '<text x="32" y="48" class="eyebrow">REPO GALAXY</text>',
        f'<text x="32" y="82" class="title">@{html.escape(USER)}</text>',
        f'<text x="32" y="106" class="stat">{total_stars} stars · {len(repos)} repositories</text>',
        '<text x="32" y="128" class="hint">Each star is a repository, sized by its stars.</text>',
        '<text x="32" y="250" class="eyebrow">LANGUAGES</text>',
    ]
    languages = []
    for r in repos:
        if r["language"] and r["language"] not in languages:
            languages.append(r["language"])
    if not languages:
        lines.append('<text x="32" y="274" class="hint">No public repos yet. New ones will light up here.</text>')
    for j, lang in enumerate(languages[:5]):
        y = 274 + j * 20
        color = LANG_COLORS.get(lang, DEFAULT_COLOR)
        lines.append(f'<circle cx="38" cy="{y - 4}" r="4" fill="{color}"/>')
        lines.append(f'<text x="50" y="{y}" class="key">{html.escape(lang)}</text>')
    return lines


def build_svg(repos):
    rng = random.Random(USER)  # same seed every day, so the galaxy keeps its shape
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        """<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0d1430"/><stop offset="1" stop-color="#060914"/>
  </linearGradient>
  <radialGradient id="core">
    <stop offset="0" stop-color="#ffffff"/><stop offset="0.25" stop-color="#c9d4ff"/>
    <stop offset="0.6" stop-color="#5b6cff" stop-opacity="0.35"/><stop offset="1" stop-color="#5b6cff" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="nebula">
    <stop offset="0" stop-color="#6d4aff" stop-opacity="0.22"/><stop offset="1" stop-color="#6d4aff" stop-opacity="0"/>
  </radialGradient>
  <filter id="blur"><feGaussianBlur stdDeviation="4"/></filter>
</defs>
<style>
  text { font-family: 'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif; }
  .eyebrow { font-size: 10px; letter-spacing: 3px; fill: #7aa2f7; font-weight: 600; }
  .title { font-size: 26px; fill: #ffffff; font-weight: 700; }
  .stat { font-size: 13px; fill: #a9b1d6; }
  .hint { font-size: 11px; fill: #565f89; }
  .key { font-size: 12px; fill: #c0caf5; }
  .label { font-size: 10px; fill: #c0caf5; opacity: 0.85; }
  .foot { font-size: 9px; fill: #3b4261; }
  @keyframes twinkle { 0%, 100% { opacity: 0.2; } 50% { opacity: 1; } }
  @keyframes pulse { 0%, 100% { opacity: 0.85; } 50% { opacity: 1; } }
  .t1 { animation: twinkle 2.6s ease-in-out infinite; }
  .t2 { animation: twinkle 3.4s ease-in-out infinite 0.8s; }
  .t3 { animation: twinkle 4.2s ease-in-out infinite 1.6s; }
  .pulse, .core { animation: pulse 3s ease-in-out infinite; }
</style>""",
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="16" fill="url(#bg)" stroke="#1f2a4d"/>',
        f'<ellipse cx="{CX}" cy="{CY}" rx="230" ry="110" fill="url(#nebula)"/>',
    ]
    parts += dust_stars(rng)
    parts += [
        f'<ellipse class="core" cx="{CX}" cy="{CY}" rx="46" ry="22" fill="url(#core)"/>',
        f'<ellipse cx="{CX}" cy="{CY}" rx="20" ry="9" fill="none" stroke="#c9d4ff" stroke-opacity="0.35"/>',
    ]
    parts += repo_stars(repos)
    parts += legend(repos)
    parts.append(f'<text x="{WIDTH - 16}" y="{HEIGHT - 14}" text-anchor="end" class="foot">updated {date.today()}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    os.makedirs("dist", exist_ok=True)
    svg = build_svg(fetch_repos())
    with open("dist/galaxy.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print("Wrote dist/galaxy.svg")
