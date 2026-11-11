"""
Snake Trail generator.

Draws your contribution graph as blue squares, then animates a little
glowing snake that zig-zags down and up every column, eating the squares
as it goes. Eaten squares vanish, then slowly grow back behind it.

Runs inside the same GitHub Action as the other cards and writes
dist/snake.svg, which your README displays.
"""

import json
import os
import random
import urllib.request

from galaxy import USER                 # reuse the username setting
from projects import aurora             # and the drifting glows

# ---------- settings you can play with ----------
STEP = 0.05          # seconds the snake spends on each square (smaller = faster)
GONE = 1.2           # seconds an eaten square stays gone
REGROW = 3.0         # seconds it takes to fade back in
TAIL = 5             # how many dots follow the head
LEVEL_COLORS = {     # square color for each activity level
    "NONE": "#161d2e", "FIRST_QUARTILE": "#1f3a66", "SECOND_QUARTILE": "#2a5596",
    "THIRD_QUARTILE": "#3a70c4", "FOURTH_QUARTILE": "#5596f0",
}
TODAY_COLOR = "#6cc4ff"
WIDTH = 800
CELL, PITCH = 10.5, 13.2         # square size, and distance from one square to the next
GRID_X, GRID_Y = 50, 100        # where the top-left square sits
# ------------------------------------------------

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionLevel weekday date } }
      }
    }
  }
}"""


def fetch_calendar():
    """Ask GitHub's GraphQL API for the past year of contributions.

    This is the same data as the green squares on your profile. GraphQL
    lets you ask for exactly the fields you want in one request.
    """
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Content-Type": "application/json", "User-Agent": "snake-trail"})
    with urllib.request.urlopen(req) as response:
        data = json.load(response)
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def snake_order(column, row):
    """Which step the snake reaches this square on.

    Even columns go top to bottom, odd columns go bottom to top, so the
    snake never has to jump: it zig-zags across the whole grid.
    """
    return column * 7 + (row if column % 2 == 0 else 6 - row)


def center(column, row):
    return GRID_X + column * PITCH + CELL / 2, GRID_Y + row * PITCH + CELL / 2


def build_svg(calendar):
    weeks = calendar["weeks"]
    columns = len(weeks)
    steps = columns * 7
    run = steps * STEP                       # how long one trip across takes
    loop = run + GONE + REGROW + 0.6         # plus time for the last squares to regrow
    height = GRID_Y + 7 * PITCH + 40
    total = calendar["totalContributions"]
    title = (f"{total:,} contributions, one continuous run" if total
             else "No contributions yet. The snake is hungry.")
    today = weeks[-1]["contributionDays"][-1]["date"] if weeks else None

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">',
        f"""<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0b1226"/><stop offset="1" stop-color="#060a16"/>
  </linearGradient>
  <radialGradient id="headglow"><stop offset="0" stop-color="#ffffff" stop-opacity="0.55"/>
    <stop offset="1" stop-color="#9cc8ff" stop-opacity="0"/></radialGradient>
  <clipPath id="frame"><rect width="{WIDTH}" height="{height}" rx="16"/></clipPath>
  <path id="route" d="{route(columns)}" fill="none"/>
</defs>
<style>
  text {{ font-family: 'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif; }}
  .eyebrow {{ font-size: 10px; letter-spacing: 3px; fill: #5ab4ff; font-weight: 700; }}
  .title {{ font-size: 17px; font-weight: 700; fill: #ffffff; }}
  .live {{ font-size: 9.5px; letter-spacing: 2px; fill: #ffffff; font-weight: 700; }}
  .panel {{ fill: #070b18; fill-opacity: 0.72; stroke: #3d4785; }}
  @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}
  .dot {{ animation: pulse 1.6s ease-in-out infinite; }}
</style>""",
        '<g clip-path="url(#frame)">',
        f'<rect width="{WIDTH}" height="{height}" fill="url(#bg)"/>',
    ]
    parts += aurora(height)
    parts += [
        '</g>',
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="16" fill="none" stroke="#2a3566"/>',
        f'<rect x="24" y="20" width="{WIDTH - 48}" height="{height - 40}" rx="14" class="panel"/>',
        '<text x="48" y="52" class="eyebrow">SNAKE TRAIL</text>',
        f'<text x="48" y="76" class="title">{title}</text>',
        f'<circle cx="{WIDTH - 92}" cy="49" r="3" fill="#ff5c7a" class="dot"/>',
        f'<text x="{WIDTH - 48}" y="52" text-anchor="end" class="live">LIVE</text>',
    ]

    # The squares. Each one blinks out when the snake reaches it, then regrows.
    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            row = day["weekday"]                       # 0 = Sunday ... 6 = Saturday
            x, y = GRID_X + col * PITCH, GRID_Y + row * PITCH
            is_today = day["date"] == today
            color = TODAY_COLOR if is_today else LEVEL_COLORS[day["contributionLevel"]]
            eaten = snake_order(col, row) * STEP / loop  # when it's eaten, as a fraction of the loop
            gone = (snake_order(col, row) * STEP + GONE) / loop
            back = (snake_order(col, row) * STEP + GONE + REGROW) / loop
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{CELL}" height="{CELL}" rx="2.5" fill="{color}">'
                f'<animate attributeName="opacity" values="1;1;0;0;1;1" '
                f'keyTimes="0;{eaten:.4f};{eaten + 0.002:.4f};{gone:.4f};{back:.4f};1" '
                f'dur="{loop:.2f}s" repeatCount="indefinite"/></rect>')

    # The tail: dots that follow the same route, each a little later and smaller.
    end = run / loop
    for k in range(TAIL, 0, -1):
        delay = k * 2 * STEP
        parts.append(
            f'<circle r="{4.4 - k * 0.6:.1f}" fill="#6ea8ff" opacity="0">'
            f'<animateMotion dur="{loop:.2f}s" begin="{delay:.2f}s" repeatCount="indefinite" '
            f'keyPoints="0;1;1" keyTimes="0;{end:.4f};1" calcMode="linear"><mpath href="#route"/></animateMotion>'
            f'<animate attributeName="opacity" dur="{loop:.2f}s" begin="{delay:.2f}s" repeatCount="indefinite" '
            f'values="{0.85 - k * 0.12:.2f};{0.85 - k * 0.12:.2f};0;0" keyTimes="0;{end:.4f};{end + 0.02:.4f};1"/>'
            f'</circle>')

    # The head: a glowing white square with two eyes.
    parts.append(
        f'<g opacity="0">'
        f'<animateMotion dur="{loop:.2f}s" repeatCount="indefinite" keyPoints="0;1;1" '
        f'keyTimes="0;{end:.4f};1" calcMode="linear"><mpath href="#route"/></animateMotion>'
        f'<animate attributeName="opacity" dur="{loop:.2f}s" repeatCount="indefinite" '
        f'values="1;1;0;0" keyTimes="0;{end:.4f};{end + 0.02:.4f};1"/>'
        f'<circle r="13" fill="url(#headglow)"/>'
        f'<rect x="-6.5" y="-6.5" width="13" height="13" rx="4" fill="#ffffff"/>'
        f'<circle cx="-2.6" cy="-0.5" r="1.4" fill="#0b1226"/>'
        f'<circle cx="2.6" cy="-0.5" r="1.4" fill="#0b1226"/>'
        f'</g>')
    parts.append("</svg>")
    return "\n".join(parts)


def route(columns):
    """The zig-zag path through the center of every square, in snake order."""
    points = []
    for col in range(columns):
        rows = range(7) if col % 2 == 0 else range(6, -1, -1)
        points += [center(col, row) for row in rows]
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points)


if __name__ == "__main__":
    os.makedirs("dist", exist_ok=True)
    with open("dist/snake.svg", "w", encoding="utf-8") as f:
        f.write(build_svg(fetch_calendar()))
    print("Wrote dist/snake.svg")
