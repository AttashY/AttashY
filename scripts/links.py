"""
Connect-with-me chips.

Reads links.txt, figures out what each link is (GitHub, LinkedIn, email,
your own site...), grabs that site's icon, and draws one glowing chip per
link. Then it rewrites the "Connect" part of README.md so every chip is
its own clickable link.

To change your links you only ever edit links.txt.
"""

import base64
import html
import os
import re
import urllib.request
from urllib.parse import urlparse

from galaxy import USER

# ---------- settings you can play with ----------
LINKS_FILE = "links.txt"
README = "README.md"
CHIP_H = 46
NAME_COLOR = "#a9a3ff"
IMAGE_BASE = f"https://raw.githubusercontent.com/{USER}/{USER}/galaxy-output/links"
# Known sites: domain -> the name shown on the chip
SITES = {
    "github.com": "GitHub", "linkedin.com": "LinkedIn", "x.com": "X", "twitter.com": "X",
    "instagram.com": "Instagram", "youtube.com": "YouTube", "tiktok.com": "TikTok",
    "twitch.tv": "Twitch", "discord.gg": "Discord", "discord.com": "Discord",
    "devpost.com": "Devpost", "leetcode.com": "LeetCode", "kaggle.com": "Kaggle",
    "huggingface.co": "Hugging Face", "medium.com": "Medium", "dev.to": "DEV",
    "gitlab.com": "GitLab", "codepen.io": "CodePen", "linktr.ee": "Linktree",
    "stackoverflow.com": "Stack Overflow", "behance.net": "Behance", "dribbble.com": "Dribbble",
}
# ------------------------------------------------


def read_links():
    """Each non-empty, non-# line of links.txt -> (custom label or None, url)."""
    links = []
    with open(LINKS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            label, _, url = line.rpartition("|")
            links.append((label.strip() or None, url.strip()))
    return links


def describe(url, label=None):
    """Work out the chip's name, handle and the domain to get an icon from.

    https://github.com/AttashY            -> GitHub,  @AttashY
    https://www.linkedin.com/in/attash    -> LinkedIn, @attash
    mailto:me@mail.com                    -> Email,   me@mail.com
    https://attash.dev                    -> Website, attash.dev
    """
    if url.startswith("mailto:"):
        address = url[len("mailto:"):]
        return label or "Email", address, address.split("@")[-1]
    parsed = urlparse(url if "://" in url else "https://" + url)
    domain = parsed.netloc.lower().removeprefix("www.")
    # the last meaningful bit of the path is usually the username
    parts = [p for p in parsed.path.split("/") if p and p not in ("in", "u", "c", "user", "users")]
    if domain in SITES:
        handle = "@" + parts[-1].lstrip("@") if parts else domain
        return label or SITES[domain], handle, domain
    return label or "Website", domain + (parsed.path.rstrip("/") if parsed.path not in ("", "/") else ""), domain


def fetch_icon(domain):
    """Download the site's little icon (favicon) and turn it into text that
    can live inside the SVG. Returns None if it can't be found."""
    try:
        url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        req = urllib.request.Request(url, headers={"User-Agent": "profile-links"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
        return "data:image/png;base64," + base64.b64encode(data).decode()
    except Exception:
        return None


def chip_svg(name, handle, icon):
    """One pill-shaped chip with a highlight that slides around its border."""
    text_w = max(len(handle) * 7.3, len(name) * 6.6)   # rough width of the text
    w = round(52 + text_w + 22)
    h = CHIP_H
    r = (h - 6) / 2
    if icon:   # the site's real icon on a white circle so dark logos still show
        badge = (f'<circle cx="26" cy="{h / 2}" r="13" fill="#ffffff"/>'
                 f'<image href="{icon}" x="17" y="{h / 2 - 9}" width="18" height="18"/>')
    else:      # no icon found: first letter instead
        badge = (f'<circle cx="26" cy="{h / 2}" r="13" fill="#2b2e40"/>'
                 f'<text x="26" y="{h / 2 + 4.5}" text-anchor="middle" class="letter">{html.escape(name[0])}</text>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>
  <linearGradient id="shine" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0.3" stop-color="#ffffff" stop-opacity="0"/>
    <stop offset="0.5" stop-color="#ffffff" stop-opacity="0.95"/>
    <stop offset="0.7" stop-color="#ffffff" stop-opacity="0"/>
    <animateTransform attributeName="gradientTransform" type="rotate"
      from="0 0.5 0.5" to="360 0.5 0.5" dur="4s" repeatCount="indefinite"/>
  </linearGradient>
</defs>
<style>
  text {{ font-family: 'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif; }}
  .name {{ font-size: 9px; font-weight: 700; fill: {NAME_COLOR}; letter-spacing: 1px; }}
  .handle {{ font-size: 12px; font-weight: 700; fill: #ffffff; }}
  .letter {{ font-size: 13px; font-weight: 800; fill: #ffffff; }}
</style>
<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="{r}" fill="#0b0c1a" stroke="#5b63c9" stroke-width="1.5"/>
<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="{r}" fill="none" stroke="url(#shine)" stroke-width="1.8"/>
{badge}
<text x="48" y="{h / 2 - 3}" class="name">{html.escape(name)}</text>
<text x="48" y="{h / 2 + 11}" class="handle">{html.escape(handle)}</text>
</svg>"""


def update_readme(entries):
    """Replace everything between the LINKS markers in README.md."""
    chips = "\n".join(
        f'  <a href="{html.escape(url)}"><img height="{CHIP_H}" src="{IMAGE_BASE}/{file}" alt="{html.escape(name)}" /></a>'
        for url, file, name in entries)
    block = f'<!-- LINKS:START -->\n<p align="center">\n{chips}\n</p>\n<!-- LINKS:END -->'
    with open(README, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"<!-- LINKS:START -->.*?<!-- LINKS:END -->", lambda _: block, text, flags=re.S)
    with open(README, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    os.makedirs("dist/links", exist_ok=True)
    entries = []
    for i, (label, url) in enumerate(read_links()):
        name, handle, domain = describe(url, label)
        file = f"{i}-{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}.svg"
        with open(f"dist/links/{file}", "w", encoding="utf-8") as f:
            f.write(chip_svg(name, handle, fetch_icon(domain)))
        entries.append((url, file, name))
    update_readme(entries)
    print(f"Made {len(entries)} link chips")
