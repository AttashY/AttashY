"""
Language Stack generator.

Draws a card with your top languages as colored bars. The numbers are
"repository-weighted": every repo counts equally, no matter how big it
is, so one giant project can't drown out everything else.

Runs inside the same GitHub Action as the galaxy and writes
dist/stack.svg, which your README displays.
"""

import html
import os

from galaxy import color_for                        # reuse code from galaxy.py
from projects import all_repos, aurora, languages_of   # and from projects.py

# ---------- settings you can play with ----------
TOP_LANGUAGES = 5      # how many rows to show
IGNORE = []            # languages to leave out, e.g. ["Jupyter Notebook"]
WIDTH = 800
ROW_GAP = 28           # space between rows
# ------------------------------------------------


def repo_weighted(language_maps):
    """Turn each repo's byte counts into shares, then average across repos.

    Example with two repos:
        repo A: {"Python": 900, "HTML": 100} -> Python 0.9, HTML 0.1
        repo B: {"JavaScript": 50}           -> JavaScript 1.0
    Average over 2 repos: JavaScript 50%, Python 45%, HTML 5%
    """
    totals, repo_count = {}, 0
    for languages in language_maps:
        languages = {k: v for k, v in languages.items() if k not in IGNORE}
        size = sum(languages.values())
        if not size:
            continue                      # empty repo, nothing to count
        repo_count += 1
        for lang, nbytes in languages.items():
            totals[lang] = totals.get(lang, 0) + nbytes / size
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return [(lang, share / repo_count) for lang, share in ranked[:TOP_LANGUAGES]]


def build_svg(stack):
    rows = max(1, len(stack))
    height = 116 + rows * ROW_GAP + 26
    panel_w, panel_h = WIDTH - 56, height - 48
    track_x, track_w = 330, WIDTH - 28 - 330 - 26
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">',
        f"""<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0b1226"/><stop offset="1" stop-color="#060a16"/>
  </linearGradient>
  <clipPath id="frame"><rect width="{WIDTH}" height="{height}" rx="16"/></clipPath>
</defs>
<style>
  text {{ font-family: 'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif; }}
  .title {{ font-size: 23px; font-weight: 800; fill: #ffffff; }}
  .sub {{ font-size: 11.5px; font-weight: 600; fill: #a9b8ff; letter-spacing: 0.4px; }}
  .cmd {{ font-size: 11.5px; font-weight: 700; fill: #8f9bff; font-family: Consolas, Menlo, 'DejaVu Sans Mono', monospace; }}
  .lang {{ font-size: 12px; font-weight: 700; fill: #ffffff; }}
  .pct {{ font-size: 11.5px; font-weight: 700; font-family: Consolas, Menlo, 'DejaVu Sans Mono', monospace; }}
  .hint {{ font-size: 12px; fill: #737aa2; }}
  .panel {{ fill: #070b18; fill-opacity: 0.72; stroke: #3d4785; }}
  .track {{ fill: #2a2f45; }}
  @keyframes blink {{ 0%, 49% {{ opacity: 1; }} 50%, 100% {{ opacity: 0; }} }}
  .cursor {{ animation: blink 1.1s step-end infinite; }}
</style>""",
        '<g clip-path="url(#frame)">',
        f'<rect width="{WIDTH}" height="{height}" fill="url(#bg)"/>',
    ]
    parts += aurora(height)   # the same drifting glows as the projects card
    parts += [
        '</g>',
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="16" fill="none" stroke="#2a3566"/>',
        f'<rect x="28" y="24" width="{panel_w}" height="{panel_h}" rx="14" class="panel"/>',
        '<text x="50" y="64" class="title">Language Stack</text>',
        '<text x="51" y="85" class="sub">Repository-weighted technologies</text>',
        f'<text x="{WIDTH - 56}" y="60" text-anchor="end" class="cmd">&gt; stack.scan'
        '<tspan class="cursor">  _</tspan></text>',
    ]
    if not stack:
        parts.append('<text x="52" y="124" class="hint">No languages detected yet. Push some code and check back tomorrow.</text>')
    for i, (lang, share) in enumerate(stack):
        y = 116 + i * ROW_GAP
        color = color_for(lang)
        fill_w = max(share * track_w, 7)
        parts += [
            f'<circle cx="56" cy="{y - 4}" r="4" fill="{color}"/>',
            f'<text x="72" y="{y}" class="lang">{html.escape(lang)}</text>',
            f'<text x="{track_x - 20}" y="{y}" text-anchor="end" class="pct" fill="{color}">{round(share * 100)}%</text>',
            f'<rect x="{track_x}" y="{y - 8}" width="{track_w}" height="7" rx="3.5" class="track"/>',
            # the colored bar grows from 0 to its full width when the image loads
            f'<rect x="{track_x}" y="{y - 8}" width="{fill_w:.1f}" height="7" rx="3.5" fill="{color}">'
            f'<animate attributeName="width" from="0" to="{fill_w:.1f}" dur="1.4s" begin="0s" '
            f'fill="freeze" calcMode="spline" keyTimes="0;1" keySplines="0.2 0.8 0.2 1"/></rect>',
        ]
    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    os.makedirs("dist", exist_ok=True)
    # your repos + ones you've contributed to, not counting the profile repo's scripts
    language_maps = [languages_of(r) for r in all_repos()]
    with open("dist/stack.svg", "w", encoding="utf-8") as f:
        f.write(build_svg(repo_weighted(language_maps)))
    print("Wrote dist/stack.svg")
