"""
Repo Galaxy generator.

Draws an animated spiral galaxy as an SVG image.
  - Each spiral ARM is one of your languages, in that language's color.
  - Each REPO is a glowing star sitting on its language's arm,
    sized by its GitHub stars.
  - Small stars drift slowly outward along the arms, like a real galaxy.

Runs inside a GitHub Action (see .github/workflows/galaxy.yml) and writes
dist/galaxy.svg, which your README displays.
"""

import colorsys
import hashlib
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
CX, CY = 505, 190                 # where the galaxy's center sits
MAX_ARMS = 4                      # most languages that get their own arm
DRIFT_STARS = 200                 # drifting stars, shared between the arms
TILT = 0.9                        # 1 = seen from above, smaller = more tilted
TURN = 200                        # rotates the whole galaxy (degrees)
DRIFT_SECONDS = (10, 18)          # how long one star takes to drift (min, max)

# Brightened versions of GitHub's language colors (the originals are hard
# to see on a dark background). Any language not listed gets its own
# color made from its name, so it's always the same.
LANG_COLORS = {
    "JavaScript": "#f7e463", "TypeScript": "#4aa3ff", "Python": "#5b9cf0",
    "Jupyter Notebook": "#ff7eb6", "HTML": "#ff6f4d", "CSS": "#a36bff",
    "SCSS": "#e66aa8", "Java": "#f0a33a", "Kotlin": "#b38cff",
    "C": "#a8b3c7", "C++": "#ff5c8a", "C#": "#4fd16a", "Go": "#3fd0e8",
    "Rust": "#e8a07a", "Ruby": "#ff4d5e", "PHP": "#8f97e0", "Swift": "#ff7a45",
    "Shell": "#8fe36b", "Astro": "#ff6a1a", "Vue": "#4fd6a0", "Dart": "#3fc6d6",
}
NO_LANGUAGE = "#c0caf5"           # repos GitHub couldn't detect a language for
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


def color_for(language):
    """A language's color. Unknown languages get a bright color from their name."""
    if language is None:
        return NO_LANGUAGE
    if language in LANG_COLORS:
        return LANG_COLORS[language]
    hue = int(hashlib.md5(language.encode()).hexdigest(), 16) % 360 / 360
    r, g, b = colorsys.hls_to_rgb(hue, 0.65, 0.85)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def language_arms(repos):
    """Pick which languages get an arm, and what share of repos each has.

    Returns a list of (language, color, share), biggest language first.
    With no repos yet, you get two plain arms so the galaxy isn't empty.
    """
    counts = {}
    for r in repos:
        if r["language"]:
            counts[r["language"]] = counts.get(r["language"], 0) + 1
    total = sum(counts.values())
    if total == 0:
        return [(None, "#7c83ff", 0.5), (None, "#7c83ff", 0.5)]
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:MAX_ARMS]
    arms = [(lang, color_for(lang), n / total) for lang, n in top]
    if len(arms) == 1:  # one language still looks better with two arms
        arms.append(arms[0])
    return arms


# ---------- the shape of the arms ----------

def arm_points(arm, arm_count):
    """Points along one arm, from the core outward.

    A logarithmic spiral: radius = a * e^(b * angle), so the arm gets
    further from the center as it winds around. Each arm is the same
    spiral, turned by 360 / arm_count degrees.
    """
    points = []
    theta = 0.0
    while theta <= 1.8 * math.pi:
        radius = 30 * math.exp(0.44 * theta)
        angle = theta + arm * (2 * math.pi / arm_count) + math.radians(TURN)
        x = CX + radius * math.cos(angle)
        y = CY + radius * math.sin(angle) * TILT
        points.append((x, y))
        theta += 0.04
    return points


def arm_lengths(points):
    """Running distance along the arm at each point (used to walk along it)."""
    lengths = [0.0]
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.hypot(x2 - x1, y2 - y1))
    return lengths


def point_on_arm(points, lengths, fraction):
    """The spot `fraction` of the way along the arm (0 = core, 1 = tip)."""
    target = fraction * lengths[-1]
    for i in range(1, len(points)):
        if lengths[i] >= target:
            step = (target - lengths[i - 1]) / (lengths[i] - lengths[i - 1] or 1)
            (x1, y1), (x2, y2) = points[i - 1], points[i]
            return x1 + (x2 - x1) * step, y1 + (y2 - y1) * step
    return points[-1]


def arm_path(points):
    """Turn the points into an SVG path, which the stars will travel along."""
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points)


# ---------- the drifting stars ----------

def make_stars(rng, arms):
    """Decide each drifting star's arm, color, route and speed.

    Bigger languages get more stars, but every arm gets at least 35
    so small languages are still visible.
    """
    stars = []
    for index, (_, color, share) in enumerate(arms):
        for _ in range(max(35, round(DRIFT_STARS * share))):
            start = rng.random() ** 1.8 * 0.9        # more stars near the core
            stars.append({
                "arm": index,
                "color": color,
                "start": start,
                "end": start + rng.uniform(0.04, 0.09),
                "seconds": rng.uniform(*DRIFT_SECONDS),
                "offset": rng.random(),              # so they don't move in sync
                "dx": rng.gauss(0, 3 + 7 * start),   # spread around the arm,
                "dy": rng.gauss(0, 3 + 7 * start),   # fuzzier further out
                "size": rng.uniform(0.9, 2.1),
                "brightness": rng.uniform(0.5, 0.95),
            })
    return stars


def star_svg(star):
    """One star that drifts along its arm, fading in and out at the ends."""
    s = star
    begin = -s["offset"] * s["seconds"]   # negative = already partway through at load
    timing = f'dur="{s["seconds"]:.1f}s" begin="{begin:.1f}s" repeatCount="indefinite"'
    return (
        f'<g transform="translate({s["dx"]:.1f} {s["dy"]:.1f})">'
        f'<circle r="{s["size"]:.2f}" fill="{s["color"]}" opacity="0">'
        f'<animateMotion {timing} keyPoints="{s["start"]:.3f};{s["end"]:.3f}" '
        f'keyTimes="0;1" calcMode="linear"><mpath href="#arm{s["arm"]}"/></animateMotion>'
        f'<animate attributeName="opacity" {timing} keyTimes="0;0.2;0.8;1" '
        f'values="0;{s["brightness"]:.2f};{s["brightness"]:.2f};0"/>'
        f'</circle></g>'
    )


def background_stars(rng):
    """Faint still stars scattered across the card."""
    out = []
    for _ in range(80):
        x, y = rng.uniform(10, WIDTH - 10), rng.uniform(10, HEIGHT - 10)
        twinkle = f' class="t{rng.randint(1, 3)}"' if rng.random() < 0.3 else ""
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rng.uniform(0.4, 1.0):.2f}" '
                   f'fill="#c0caf5" opacity="{rng.uniform(0.15, 0.45):.2f}"{twinkle}/>')
    return out


# ---------- your repos ----------

def overlaps(box, boxes):
    """True if a rectangle (left, top, right, bottom) touches any in the list."""
    l, t, r, b = box
    return any(l < R and r > L and t < B and b > T for L, T, R, B in boxes)


def repo_stars(repos, arms, arm_shapes):
    """One glowing star per repo, on its own language's arm.

    Repos whose language has no arm (or no language) take turns on the
    arms. Each repo starts near the core and slides outward along its
    arm until its star and label don't overlap anything already placed.
    """
    out = []
    arm_of = {lang: i for i, (lang, _, _) in enumerate(arms) if lang}
    taken = [(CX - 38, CY - 20, CX + 38, CY + 20),   # the core
             (0, 0, 250, HEIGHT)]                      # the text on the left
    spare = 0
    repos = sorted(repos, key=lambda r: r["stargazers_count"], reverse=True)
    for i, repo in enumerate(repos):
        if repo["language"] in arm_of:
            arm = arm_of[repo["language"]]
        else:
            arm = spare % len(arms)
            spare += 1
        points, lengths = arm_shapes[arm]
        size = min(3.2 + 2.2 * math.sqrt(repo["stargazers_count"]), 12)
        name = repo["name"] if len(repo["name"]) <= 20 else repo["name"][:19] + "…"
        labelled = i < 10  # label the top 10 so it doesn't get cluttered
        label_width = (len(name) + 4) * 6.2 if labelled else 0

        fraction = 0.05
        while True:  # walk outward until there's a free spot
            x, y = point_on_arm(points, lengths, fraction)
            box = (x - size - 3, y - max(size, 7) - 2, x + size + 6 + label_width, y + max(size, 7) + 2)
            on_card = box[0] > 0 and box[2] < WIDTH - 8 and box[1] > 8 and box[3] < HEIGHT - 8
            if (on_card and not overlaps(box, taken)) or fraction > 0.85:
                break
            fraction += 0.02
        taken.append(box)

        color = color_for(repo["language"])
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size * 2.4:.1f}" '
                   f'fill="{color}" opacity="0.22" filter="url(#blur)"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size:.1f}" fill="{color}" class="pulse"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size * 0.4:.1f}" fill="#ffffff" opacity="0.9"/>')
        if labelled:
            out.append(f'<text x="{x + size + 5:.1f}" y="{y + 3.5:.1f}" class="label">'
                       f'{html.escape(name)} <tspan class="dim">★ {repo["stargazers_count"]}</tspan></text>')
    return out


def legend(repos, arms):
    """Left-side panel: title, totals and the arm (language) key."""
    total_stars = sum(r["stargazers_count"] for r in repos)
    lines = [
        '<text x="32" y="48" class="eyebrow">REPO GALAXY</text>',
        f'<text x="32" y="82" class="title">@{html.escape(USER)}</text>',
        f'<text x="32" y="106" class="stat">{total_stars} stars · {len(repos)} repositories</text>',
        '<text x="32" y="128" class="hint">Each star is a repository, sized by its stars.</text>',
        '<text x="32" y="222" class="eyebrow">ARMS</text>',
    ]
    shown = [a for a in dict.fromkeys(arms) if a[0]]  # drop the duplicate / plain arms
    if not shown:
        lines.append('<text x="32" y="246" class="hint">No public repos yet. New ones will light up here.</text>')
    for j, (lang, color, share) in enumerate(shown):
        y = 246 + j * 22
        lines.append(f'<circle cx="38" cy="{y - 4}" r="4.5" fill="{color}"/>')
        lines.append(f'<text x="52" y="{y}" class="key">{html.escape(lang)}</text>')
        lines.append(f'<text x="200" y="{y}" text-anchor="end" class="pct">{round(share * 100)}%</text>')
    return lines


# ---------- putting it together ----------

def build_svg(repos):
    rng = random.Random(USER)  # same seed every day, so the galaxy keeps its shape
    arms = language_arms(repos)
    arm_shapes = [(p, arm_lengths(p)) for p in (arm_points(a, len(arms)) for a in range(len(arms)))]
    paths = "".join(f'<path id="arm{a}" d="{arm_path(arm_shapes[a][0])}" fill="none"/>'
                    for a in range(len(arms)))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        f"""<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0b1226"/><stop offset="0.5" stop-color="#0e1730"/>
    <stop offset="1" stop-color="#050913"/>
  </linearGradient>
  <filter id="blur"><feGaussianBlur stdDeviation="4"/></filter>
  <clipPath id="card"><rect width="{WIDTH}" height="{HEIGHT}" rx="16"/></clipPath>
  {paths}
</defs>
<style>
  text {{ font-family: 'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif; }}
  .eyebrow {{ font-size: 10px; letter-spacing: 3px; fill: #7aa2f7; font-weight: 600; }}
  .title {{ font-size: 26px; fill: #ffffff; font-weight: 700; }}
  .stat {{ font-size: 13px; fill: #a9b1d6; }}
  .hint {{ font-size: 11px; fill: #565f89; }}
  .key {{ font-size: 12px; fill: #e0e6ff; font-weight: 600; }}
  .pct {{ font-size: 11px; fill: #a9b1d6; font-family: Consolas, 'Courier New', monospace; }}
  .label {{ font-size: 10.5px; fill: #ffffff; font-weight: 600; }}
  .dim {{ fill: #a9b1d6; font-weight: 400; }}
  .foot {{ font-size: 9px; fill: #3b4261; }}
  @keyframes twinkle {{ 0%, 100% {{ opacity: 0.15; }} 50% {{ opacity: 0.8; }} }}
  @keyframes pulse {{ 0%, 100% {{ opacity: 0.85; }} 50% {{ opacity: 1; }} }}
  .t1 {{ animation: twinkle 2.6s ease-in-out infinite; }}
  .t2 {{ animation: twinkle 3.4s ease-in-out infinite 0.8s; }}
  .t3 {{ animation: twinkle 4.2s ease-in-out infinite 1.6s; }}
  .pulse {{ animation: pulse 3s ease-in-out infinite; }}
</style>""",
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="16" fill="url(#bg)" stroke="#1f2a4d"/>',
        '<g clip-path="url(#card)">',   # anything past the card's edge gets cut off
    ]
    parts += background_stars(rng)
    parts += [  # the core: a soft halo, a brighter ring and a white center
        f'<ellipse cx="{CX}" cy="{CY}" rx="34" ry="17" fill="#3b4a9a" opacity="0.35"/>',
        f'<ellipse cx="{CX}" cy="{CY}" rx="14" ry="7" fill="#6c7ad6" opacity="0.55"/>',
        f'<circle cx="{CX}" cy="{CY}" r="3.5" fill="#ffffff"/>',
    ]
    parts += [star_svg(s) for s in make_stars(rng, arms)]
    parts += repo_stars(repos, arms, arm_shapes)
    parts.append("</g>")
    parts += legend(repos, arms)
    parts.append(f'<text x="{WIDTH - 16}" y="{HEIGHT - 14}" text-anchor="end" class="foot">updated {date.today()}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    os.makedirs("dist", exist_ok=True)
    svg = build_svg(fetch_repos())
    with open("dist/galaxy.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print("Wrote dist/galaxy.svg")
