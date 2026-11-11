"""
Profile stats generator.

Draws three cards from the same GitHub data:
  - signal.svg:     Stars, Contributions, Repos and Followers in four tiles
  - streak.svg:     all-time contributions, current and longest streak
  - activity.svg:   your contribution graph, revealed by a scanning line

Runs inside the same GitHub Action as the other cards.
"""

import json
import math
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone

from galaxy import USER, fetch_repos     # reuse code from the other scripts
from projects import aurora, get_json
from snake import LEVEL_COLORS, TODAY_COLOR, fetch_calendar

# ---------- settings you can play with ----------
W, H = 400, 180                 # each card's size
TILE_COLORS = {"Stars": "#4aa3ff", "Contributions": "#22d3ee",
               "Repos": "#b77bff", "Followers": "#4ade80"}
STREAK_BG = "#001a2e"           # streak card colors, matching your reference
RING = "#e0a3ff"
FIRE = "#fff176"
DATES = "#a8f0ff"
# ------------------------------------------------

DAYS_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""


def graphql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Content-Type": "application/json", "User-Agent": "profile-stats"})
    with urllib.request.urlopen(req) as response:
        return json.load(response)["data"]


def fetch_all_days(created, now):
    """Every day since the account was made, with its contribution count.

    GitHub only answers for up to one year per question, so we ask once
    per calendar year and glue the answers together.
    """
    days = {}
    for year in range(created.year, now.year + 1):
        start = max(created, datetime(year, 1, 1, tzinfo=timezone.utc))
        end = min(now, datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
        data = graphql(DAYS_QUERY, {"login": USER, "from": start.isoformat(), "to": end.isoformat()})
        for week in data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                days[date.fromisoformat(day["date"])] = day["contributionCount"]
    return sorted(days.items())


def streaks(days):
    """Work out total, current streak and longest streak from (date, count) pairs.

    A streak is a run of days in a row with at least one contribution.
    Today doesn't break your streak if you haven't committed yet; the
    current streak counts back from yesterday in that case.
    """
    total = sum(count for _, count in days)

    longest, longest_range = 0, None
    run_start, run = None, 0
    for day, count in days:
        if count > 0:
            run_start = day if run == 0 else run_start
            run += 1
            if run > longest:
                longest, longest_range = run, (run_start, day)
        else:
            run = 0

    current, current_range = 0, None
    i = len(days) - 1
    if i >= 0 and days[i][1] == 0:
        i -= 1                                # no commits today yet: start from yesterday
    end = days[i][0] if i >= 0 else None
    while i >= 0 and days[i][1] > 0:
        current += 1
        current_range = (days[i][0], end)
        i -= 1
    return total, (current, current_range), (longest, longest_range)


def nice_date(d, today):
    """Nov 7  or  Dec 31, 2025  (the year only shows if it isn't this year)."""
    text = f"{d:%b} {d.day}"
    return text if d.year == today.year else f"{text}, {d.year}"


def nice_range(r, today):
    if r is None:
        return "No streak yet"
    start, end = r
    if start == end:
        return nice_date(start, today)
    return f"{nice_date(start, today)} - {nice_date(end, today)}"


# ---------- card 1: Profile Signal ----------

def signal_svg(stats):
    biggest = max(stats.values()) or 1
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f"""<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0b1226"/><stop offset="1" stop-color="#060a16"/>
  </linearGradient>
  <clipPath id="frame"><rect width="{W}" height="{H}" rx="14"/></clipPath>
  <path id="orbit" d="M 300 52 C 340 40, 380 60, 350 80 C 320 100, 270 70, 300 52 Z"/>
</defs>
<style>
  text {{ font-family: 'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif; }}
  .title {{ font-size: 18px; font-weight: 800; fill: #ffffff; }}
  .sub {{ font-size: 9px; font-weight: 600; fill: #8a93b8; letter-spacing: 0.6px; }}
  .label {{ font-size: 8.5px; font-weight: 700; fill: #c0caf5; letter-spacing: 0.2px; }}
  .value {{ font-size: 20px; font-weight: 800; }}
  .tile {{ fill: #070b18; fill-opacity: 0.75; stroke: #2f3a6b; }}
  .panel {{ fill: #070b18; fill-opacity: 0.55; stroke: #2f3a6b; }}
  .track {{ fill: #22283d; }}
</style>""",
        '<g clip-path="url(#frame)">',
        f'<rect width="{W}" height="{H}" fill="url(#bg)"/>',
    ]
    parts += aurora(H, W)
    parts += [
        '</g>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="#2a3566"/>',
        f'<rect x="12" y="12" width="{W - 24}" height="{H - 24}" rx="11" class="panel"/>',
        '<text x="26" y="42" class="title">Profile Signal</text>',
        '<text x="27" y="58" class="sub">Live GitHub stats · updated daily</text>',
        # a little "signal" blip circling in the corner
        '<circle r="2" fill="#7aa2f7"><animateMotion dur="9s" repeatCount="indefinite">'
        '<mpath href="#orbit"/></animateMotion>'
        '<animate attributeName="opacity" values="0.3;1;0.3" dur="2s" repeatCount="indefinite"/></circle>',
    ]
    tile_w, gap = (W - 48 - 3 * 8) / 4, 8
    for i, (label, value) in enumerate(stats.items()):
        x = 24 + i * (tile_w + gap)
        color = TILE_COLORS[label]
        bar = max(value / biggest * (tile_w - 20), 5)   # bars compare the four numbers
        parts += [
            f'<rect x="{x:.1f}" y="72" width="{tile_w:.1f}" height="84" rx="9" class="tile"/>',
            f'<text x="{x + 10:.1f}" y="92" class="label">{label}</text>',
            f'<text x="{x + 10:.1f}" y="122" class="value" fill="{color}">{value:,}</text>',
            f'<rect x="{x + 10:.1f}" y="138" width="{tile_w - 20:.1f}" height="5" rx="2.5" class="track"/>',
            f'<rect x="{x + 10:.1f}" y="138" width="{bar:.1f}" height="5" rx="2.5" fill="{color}">'
            f'<animate attributeName="width" from="0" to="{bar:.1f}" dur="1.4s" fill="freeze" '
            f'calcMode="spline" keyTimes="0;1" keySplines="0.2 0.8 0.2 1"/></rect>',
        ]
    parts.append("</svg>")
    return "\n".join(parts)


# ---------- card 2: Streak ----------

def streak_svg(total, since, current, longest, today):
    cur_days, cur_range = current
    long_days, long_range = longest
    r = 32
    circumference = 2 * math.pi * r
    gap = 30                                   # the opening at the top for the flame
    ring = circumference - gap
    gap_angle = gap / circumference * 360
    cx, cy = W / 2, 74
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f"""<style>
  text {{ font-family: 'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif; text-anchor: middle; }}
  .big {{ font-size: 24px; font-weight: 700; fill: {RING}; }}
  .label {{ font-size: 12px; fill: {RING}; }}
  .dates {{ font-size: 10.5px; fill: {DATES}; }}
  .fire {{ font-size: 24px; font-weight: 700; fill: {FIRE}; }}
  .firelabel {{ font-size: 12px; font-weight: 700; fill: {FIRE}; }}
  @keyframes flicker {{ 0%, 100% {{ transform: scale(1); }} 50% {{ transform: scale(1.12, 0.92); }} }}
  .flame {{ transform-origin: {cx}px 48px; animation: flicker 1.2s ease-in-out infinite; }}
</style>""",
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="{STREAK_BG}" stroke="#0e2a44"/>',
        # dividers
        f'<line x1="{W / 3:.0f}" y1="36" x2="{W / 3:.0f}" y2="{H - 36}" stroke="#8b9bb4" stroke-width="1.5"/>',
        f'<line x1="{2 * W / 3:.0f}" y1="36" x2="{2 * W / 3:.0f}" y2="{H - 36}" stroke="#8b9bb4" stroke-width="1.5"/>',
        # left: total contributions
        f'<text x="{W / 6:.0f}" y="88" class="big">{total:,}</text>',
        f'<text x="{W / 6:.0f}" y="114" class="label">Total Contributions</text>',
        f'<text x="{W / 6:.0f}" y="138" class="dates">{nice_date(since, today)} - Present</text>',
        # middle: ring with a gap at the top, drawn in when the image loads
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{RING}" stroke-width="4" '
        f'stroke-linecap="round" stroke-dasharray="{ring:.1f} {circumference:.1f}" '
        f'transform="rotate({-90 + gap_angle / 2:.1f} {cx} {cy})">'
        f'<animate attributeName="stroke-dashoffset" from="{ring:.1f}" to="0" dur="1.2s" fill="freeze" '
        f'calcMode="spline" keyTimes="0;1" keySplines="0.2 0.8 0.2 1"/></circle>',
        # the flame: an outer teardrop with a hole in the middle
        f'<g class="flame"><path fill="{RING}" fill-rule="evenodd" d="M {cx} 33 '
        f'C {cx + 9} 41, {cx + 9} 51, {cx} 53 C {cx - 9} 51, {cx - 9} 43, {cx - 4} 38 '
        f'C {cx - 3} 42, {cx - 1} 43, {cx} 42 C {cx + 2} 39, {cx + 1} 36, {cx} 33 Z '
        f'M {cx} 44 C {cx + 3} 46, {cx + 3} 50, {cx} 50 C {cx - 3} 50, {cx - 3} 47, {cx} 44 Z"/></g>',
        f'<text x="{cx}" y="{cy + 9}" class="fire">{cur_days}</text>',
        f'<text x="{cx}" y="128" class="firelabel">Current Streak</text>',
        f'<text x="{cx}" y="150" class="dates">{nice_range(cur_range, today)}</text>',
        # right: longest streak
        f'<text x="{5 * W / 6:.0f}" y="88" class="big">{long_days}</text>',
        f'<text x="{5 * W / 6:.0f}" y="114" class="label">Longest Streak</text>',
        f'<text x="{5 * W / 6:.0f}" y="138" class="dates">{nice_range(long_range, today)}</text>',
        "</svg>",
    ])


# ---------- card 3: Contribution Activity ----------

def activity_svg(calendar):
    """Your contribution graph. When the image loads, a glowing line sweeps
    left to right and each column fades in as the line passes it."""
    width = 800
    cell, pitch = 10.5, 13.2
    gx, gy = 50, 102
    weeks = calendar["weeks"]
    columns = max(len(weeks), 1)
    grid_w = columns * pitch
    height = gy + 7 * pitch + 42
    sweep = 1.8                                  # seconds for the line to cross
    total = calendar["totalContributions"]
    today = weeks[-1]["contributionDays"][-1]["date"] if weeks else None
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f"""<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0b1226"/><stop offset="1" stop-color="#060a16"/>
  </linearGradient>
  <linearGradient id="beam" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#5ab4ff" stop-opacity="0"/>
    <stop offset="0.8" stop-color="#5ab4ff" stop-opacity="0.35"/>
    <stop offset="1" stop-color="#5ab4ff" stop-opacity="0"/>
  </linearGradient>
  <clipPath id="frame"><rect width="{width}" height="{height}" rx="16"/></clipPath>
</defs>
<style>
  text {{ font-family: 'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif; }}
  .title {{ font-size: 20px; font-weight: 800; fill: #ffffff; }}
  .sub {{ font-size: 11.5px; font-weight: 600; fill: #a9b1d6; }}
  .legend {{ font-size: 10px; fill: #a9b1d6; }}
  .panel {{ fill: #070b18; fill-opacity: 0.72; stroke: #3d4785; }}
  @keyframes glow {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.55; }} }}
  .today {{ animation: glow 2s ease-in-out infinite; }}
</style>""",
        '<g clip-path="url(#frame)">',
        f'<rect width="{width}" height="{height}" fill="url(#bg)"/>',
    ]
    parts += aurora(height, width)
    parts += [
        '</g>',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="16" fill="none" stroke="#2a3566"/>',
        f'<rect x="24" y="22" width="{width - 48}" height="{height - 44}" rx="14" class="panel"/>',
        '<text x="48" y="62" class="title">Contribution Activity</text>',
        f'<text x="49" y="82" class="sub">{total:,} contribution{"" if total == 1 else "s"} in the last year</text>',
    ]
    # the Less ■■■■■ More legend
    lx = width - 48 - 5 * 13 - 60
    parts.append(f'<text x="{lx}" y="62" class="legend">Less</text>')
    for i, color in enumerate(LEVEL_COLORS.values()):
        parts.append(f'<rect x="{lx + 28 + i * 13}" y="53" width="10" height="10" rx="2.5" fill="{color}"/>')
    parts.append(f'<text x="{lx + 28 + 5 * 13 + 4}" y="62" class="legend">More</text>')

    # the squares, one column (week) at a time
    for col, week in enumerate(weeks):
        arrive = (col + 0.5) / columns * sweep      # when the line reaches this column
        parts.append(f'<g opacity="1"><animate attributeName="opacity" values="0;0;1" '
                     f'keyTimes="0;{arrive / (sweep + 0.3):.3f};1" dur="{sweep + 0.3:.2f}s" fill="freeze"/>')
        for day in week["contributionDays"]:
            x, y = gx + col * pitch, gy + day["weekday"] * pitch
            if day["date"] == today:
                parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="2.5" '
                             f'fill="{TODAY_COLOR}" class="today"/>')
            else:
                parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="2.5" '
                             f'fill="{LEVEL_COLORS[day["contributionLevel"]]}"/>')
        parts.append('</g>')

    # the scanning line: a soft glow trailing a thin bright line
    beam_h = 7 * pitch + 6
    parts.append(
        f'<g opacity="0">'
        f'<animate attributeName="opacity" values="1;1;0" keyTimes="0;0.85;1" dur="{sweep + 0.3:.2f}s" fill="freeze"/>'
        f'<animateTransform attributeName="transform" type="translate" from="0 0" to="{grid_w:.1f} 0" '
        f'dur="{sweep:.2f}s" fill="freeze"/>'
        f'<rect x="{gx - 34}" y="{gy - 5}" width="34" height="{beam_h:.1f}" fill="url(#beam)"/>'
        f'<rect x="{gx - 2}" y="{gy - 5}" width="2" height="{beam_h:.1f}" rx="1" fill="#7cc4ff"/>'
        f'</g>')
    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    os.makedirs("dist", exist_ok=True)
    now = datetime.now(timezone.utc)
    user = get_json(f"https://api.github.com/users/{USER}")
    created = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))
    repos = fetch_repos()
    calendar = fetch_calendar()                      # the past year, day by day
    stars = sum(r["stargazers_count"] for r in repos)
    stats = {
        "Stars": stars,
        "Contributions": calendar["totalContributions"],
        "Repos": len(repos),
        "Followers": user["followers"],
    }
    total, current, longest = streaks(fetch_all_days(created, now))
    cards = {
        "signal.svg": signal_svg(stats),
        "streak.svg": streak_svg(total, created.date(), current, longest, now.date()),
        "activity.svg": activity_svg(calendar),
    }
    for name, svg in cards.items():
        with open(f"dist/{name}", "w", encoding="utf-8") as f:
            f.write(svg)
    print("Wrote", ", ".join(cards))
