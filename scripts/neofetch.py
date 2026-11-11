"""
Neofetch header.

Draws a terminal that runs `neofetch`: your GitHub profile picture turned
into ASCII art on the left, and facts about you on the right. When the
image loads, it prints line by line like a real terminal.

Needs Pillow (an image library) to read your profile picture. The
workflow installs it before running this script.
"""

import html
import io
import os
import urllib.request
from datetime import datetime, timezone

from PIL import Image, ImageOps

from galaxy import USER, add_languages, fetch_repos, language_arms
from projects import get_json
from snake import fetch_calendar
from stats import fetch_all_days, streaks

# ---------- settings you can play with ----------
ROLE = "CS student @UCalgary·aspiring AI/ML engineer"
ART_COLS = 62                   # how wide the ASCII picture is, in characters
RAMP = " .,:;-=+*#%$@"          # characters from darkest to brightest
ART_COLOR = "#3fb950"
WIDTH = 800
INFO_W = 48                     # characters per line on the right side
# ------------------------------------------------

ART_FS, ART_LH = 8.4, 9.6       # font size / line height of the picture
INFO_FS, INFO_LH = 13, 19       # font size / line height of the facts
PROMPT_FS = 13
CHAR = 0.6                      # a monospace character is about 0.6 × its font size wide


def avatar_ascii(url):
    """Download the profile picture and turn every few pixels into a character.

    Brighter spots get "heavier" characters like @ and $, darker spots get
    light ones like . and :, and black becomes a space.
    """
    with urllib.request.urlopen(url + "&s=240") as response:
        img = Image.open(io.BytesIO(response.read())).convert("RGBA")
    background = Image.new("RGBA", img.size, (0, 0, 0, 255))
    img = Image.alpha_composite(background, img).convert("L")   # to greyscale
    img = ImageOps.autocontrast(img, cutoff=2)                   # stretch darks and lights
    # characters are about twice as tall as they are wide, so squash the rows
    rows = round(ART_COLS * (CHAR * ART_FS) / ART_LH * img.height / img.width)
    img = img.resize((ART_COLS, rows))
    lines = []
    for y in range(rows):
        line = ""
        for x in range(ART_COLS):
            brightness = img.getpixel((x, y))                     # 0 (black) to 255 (white)
            line += RAMP[brightness * len(RAMP) // 256]
        lines.append(line.rstrip())
    return lines


def dotted(label, value, width):
    """'. Repos: ........ 1'  — dots fill the space between label and value."""
    start = f". {label}: "
    value = str(value)
    dots = max(width - len(start) - len(value) - 1, 2)
    return f"{start}{'.' * dots} {value}"


def heading(title, width):
    return f"- {title} " + "─" * (width - len(title) - 3)


def uptime(created, now):
    months = (now.year - created.year) * 12 + now.month - created.month
    years, months = divmod(max(months, 0), 12)
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    parts.append(f"{months} month{'s' if months != 1 else ''}")
    return ", ".join(parts) + " on GitHub"


def contact_lines():
    """Your links from links.txt, so the header always matches your Connect section."""
    try:
        from links import describe, read_links
        found = [describe(url, label) for label, url in read_links()]
    except FileNotFoundError:
        found = []
    if not found:
        found = [("GitHub", f"github.com/{USER.lower()}", "")]
    lines = []
    for name, handle, _ in found[:4]:
        if name == "GitHub":
            handle = f"github.com/{USER.lower()}"
        lines.append(dotted(name, handle, INFO_W))
    return lines


def info_lines(user, repos, calendar, current, longest, now):
    created = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))
    languages = [lang for lang, _, _ in dict.fromkeys(language_arms(repos)) if lang]
    active_days = sum(1 for w in calendar["weeks"] for d in w["contributionDays"]
                      if d["contributionLevel"] != "NONE")
    half = (INFO_W - 3) // 2
    pair = lambda a, b: f"{dotted(a[0], a[1], half)} | {dotted(b[0], b[1], INFO_W - half - 1)[2:]}"
    title = f"{USER.lower()}@github"
    return [
        ("title", f"{title} " + "─" * (INFO_W - len(title) - 1)),
        ("row", dotted("Name", user["name"] or USER, INFO_W)),
        ("row", dotted("Role", ROLE, INFO_W)),
        ("row", dotted("Uptime", uptime(created, now), INFO_W)),
        ("row", dotted("Languages", ", ".join(languages[:3]) or "—", INFO_W)),
        ("gap", ""),
        ("head", heading("Contact", INFO_W)),
        *[("row", line) for line in contact_lines()],
        ("gap", ""),
        ("head", heading("GitHub Stats", INFO_W)),
        ("row", pair(("Repos", len(repos)), ("Stars", sum(r["stargazers_count"] for r in repos)))),
        ("row", pair(("Followers", user["followers"]), ("Following", user["following"]))),
        ("row", pair(("Contributions", calendar["totalContributions"]), ("Active days", active_days))),
        ("row", pair(("Streak", f"{current}d"), ("Best streak", f"{longest}d"))),
    ]


def fixed_width(text, font_size):
    """Make a line exactly as wide as its characters should be.

    Every computer has slightly different monospace fonts, so text can come
    out a bit wider or narrower than planned. textLength tells the browser
    the exact width to use, so the picture and columns always line up.
    """
    return f'textLength="{len(text) * CHAR * font_size:.1f}" lengthAdjust="spacing"'


def reveal(start, length=0.0):
    """Animation that keeps something hidden until `start` seconds, then shows it."""
    total = 3.6                                   # the whole print-out takes this long
    a = min(start / total, 0.999)
    return (f'<animate attributeName="opacity" values="0;0;1" keyTimes="0;{a:.3f};1" '
            f'dur="{total}s" fill="freeze" calcMode="discrete"/>')


def type_out(clip_id, x, y, w, start, seconds):
    """A clip rectangle that grows from 0 to full width: makes text look typed."""
    return (f'<clipPath id="{clip_id}"><rect x="{x}" y="{y - INFO_FS}" height="{INFO_LH + 2}" width="0">'
            f'<animate attributeName="width" values="0;0;{w:.0f}" '
            f'keyTimes="0;{start / (start + seconds):.3f};1" dur="{start + seconds:.2f}s" fill="freeze"/>'
            f'</rect></clipPath>')


def build_svg(art, info):
    left, top = 36, 66
    art_w = ART_COLS * CHAR * ART_FS
    info_x = left + art_w + 30
    art_h = len(art) * ART_LH
    info_h = len(info) * INFO_LH
    body = max(art_h, info_h)
    height = top + body + 52
    prompt_user = f"{USER.lower()}@github"
    cmd_x = left + len(prompt_user + ":~$ ") * CHAR * PROMPT_FS
    cmd_w = len("neofetch") * CHAR * PROMPT_FS
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height:.0f}" viewBox="0 0 {WIDTH} {height:.0f}">',
        f"""<style>
  text {{ font-family: 'JetBrains Mono', Consolas, Menlo, 'DejaVu Sans Mono', 'Courier New', monospace; white-space: pre; }}
  .art {{ font-size: {ART_FS}px; fill: {ART_COLOR}; }}
  .info {{ font-size: {INFO_FS}px; fill: #e6edf3; }}
  .title {{ font-size: {INFO_FS}px; fill: #58a6ff; font-weight: 700; }}
  .head {{ font-size: {INFO_FS}px; fill: #58a6ff; }}
  .label {{ fill: #79c0ff; }}
  .user {{ font-size: {PROMPT_FS}px; fill: #58a6ff; font-weight: 700; }}
  .cmd {{ fill: #e6edf3; font-weight: 400; }}
  @keyframes blink {{ 0%, 49% {{ opacity: 1; }} 50%, 100% {{ opacity: 0; }} }}
  .cursor {{ animation: blink 1.1s step-end infinite; }}
</style>""",
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1:.0f}" rx="10" fill="#0d1117" stroke="#3d4785"/>',
        # first prompt. A dark box covers "neofetch" and slides right, so it looks typed.
        f'<text x="{left}" y="36" class="user" xml:space="preserve" '
        f'{fixed_width(prompt_user + ":~$ neofetch", PROMPT_FS)}>{prompt_user}'
        f'<tspan class="cmd">:~$ neofetch</tspan></text>',
        f'<rect x="{cmd_x:.1f}" y="20" width="{cmd_w + 10:.1f}" height="22" fill="#0d1117">'
        f'<animate attributeName="x" values="{cmd_x:.1f};{cmd_x:.1f};{cmd_x + cmd_w + 4:.1f}" '
        f'keyTimes="0;0.25;1" dur="0.6s" fill="freeze"/></rect>',
    ]
    # the picture prints top to bottom
    for i, line in enumerate(art):
        y = top + i * ART_LH
        parts.append(f'<text x="{left}" y="{y:.1f}" class="art" xml:space="preserve" '
                     f'{fixed_width(line, ART_FS)}>{reveal(0.7 + i * 0.05)}{html.escape(line)}</text>')
    # the facts type out one line at a time, alongside the picture
    for i, (kind, line) in enumerate(info):
        y = top + 4 + (body - info_h) / 2 + i * INFO_LH   # centered next to the picture
        start = 0.75 + i * 0.13
        if kind == "gap":
            continue
        w = len(line) * CHAR * INFO_FS * 1.1 + 30   # a little extra so nothing gets cut off
        parts.append(type_out(f"t{i}", info_x, y, w, start, 0.18))
        if kind == "row":   # color the label part of ". Label: ...."
            label, _, rest = line.partition(":")
            body_text = (f'<tspan class="label">{html.escape(label)}:</tspan>{html.escape(rest)}')
        else:
            body_text = html.escape(line)
        cls = {"title": "title", "head": "head"}.get(kind, "info")
        parts.append(f'<text x="{info_x:.1f}" y="{y:.1f}" class="{cls}" xml:space="preserve" '
                     f'{fixed_width(line, INFO_FS)} clip-path="url(#t{i})">{body_text}</text>')
    # the prompt that comes back at the end, with a blinking cursor
    end_y = top + body + 22
    done = 0.9 + max(len(art) * 0.05, len(info) * 0.13)
    parts.append(f'<g>{reveal(done)}<text x="{left}" y="{end_y:.1f}" class="user" xml:space="preserve" '
                 f'{fixed_width(prompt_user + ":~$ █", PROMPT_FS)}>{prompt_user}'
                 f'<tspan class="cmd">:~$ </tspan><tspan class="cursor" fill="#e6edf3">█</tspan></text></g>')
    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    os.makedirs("dist", exist_ok=True)
    now = datetime.now(timezone.utc)
    user = get_json(f"https://api.github.com/users/{USER}")
    repos = add_languages(fetch_repos())
    calendar = fetch_calendar()
    created = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))
    _, (current, _), (longest, _) = streaks(fetch_all_days(created, now))
    art = avatar_ascii(user["avatar_url"])
    with open("dist/neofetch.svg", "w", encoding="utf-8") as f:
        f.write(build_svg(art, info_lines(user, repos, calendar, current, longest, now)))
    print("Wrote dist/neofetch.svg")
