"""Build the profile README images from scripts/profile.toml.

    python scripts/build_assets.py           # rebuild assets/ and README blocks
    python scripts/build_assets.py --check   # exit 1 if anything is out of date

Every image is written twice: a wide version for desktop and a narrow version
that GitHub shows on phones and small windows. Text is converted to vector
outlines using the fonts in scripts/fonts, so the SVGs look identical on every
OS and need no web fonts or third-party image services.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSETS = ROOT / "assets"
README = ROOT / "README.md"

# Below GitHub's "lg" breakpoint (1012px) the README column on a profile page is
# too narrow for the wide images, so the narrow ones are served instead.
NARROW = "(max-width: 1011px)"

WIDE_W = 860
NARROW_W = 400


def f(n: float, p: int = 2) -> str:
    """Compact number formatting for SVG attributes."""
    s = f"{round(n, p):.{p}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


# ================================================================ fonts
class Font:
    def __init__(self, filename: str, key: str):
        self.tt = TTFont(HERE / "fonts" / filename)
        self.gs = self.tt.getGlyphSet()
        self.cmap = self.tt.getBestCmap()
        self.upem = self.tt["head"].unitsPerEm
        self.hmtx = self.tt["hmtx"]
        self.key = key

    def gname(self, ch: str) -> str:
        return self.cmap.get(ord(ch)) or self.cmap[ord("?")]

    def adv(self, ch: str, size: float) -> float:
        return self.hmtx[self.gname(ch)][0] * size / self.upem

    def width(self, text: str, size: float, ls: float = 0.0) -> float:
        return sum(self.adv(c, size) + ls for c in text) - (ls if text else 0)

    def path(self, glyph: str) -> str:
        pen = SVGPathPen(self.gs, ntos=lambda x: f(x, 0))
        self.gs[glyph].draw(pen)
        return pen.getCommands()


F = {
    "reg": Font("Inter-Regular.otf", "ir"),
    "med": Font("Inter-Medium.otf", "im"),
    "semi": Font("Inter-SemiBold.otf", "is"),
    "bold": Font("Inter-Bold.otf", "ib"),
    "mono": Font("DejaVuSansMono.ttf", "mr"),
    "monob": Font("DejaVuSansMono-Bold.ttf", "mb"),
}


class Doc:
    """Collects glyph outlines so each glyph is stored once per SVG."""

    def __init__(self):
        self.glyphs: dict[str, str] = {}

    def text(self, font, s, x, y, size, *, ls=0.0, anchor="start", fill=None, delay=None):
        """Outlined text; returns (svg, width). `delay(i)` staggers each
        character's appearance (typing effect)."""
        w = font.width(s, size, ls)
        if anchor == "middle":
            x -= w / 2
        elif anchor == "end":
            x -= w
        k = size / font.upem
        uses, cx = [], 0.0
        for i, ch in enumerate(s):
            if ch != " ":
                g = font.gname(ch)
                gid = font.key + re.sub(r"[^A-Za-z0-9]", "_", g)
                if gid not in self.glyphs:
                    self.glyphs[gid] = font.path(g)
                extra = ""
                if delay is not None:
                    extra = f' class="t" style="animation-delay:{f(delay(i))}s"'
                uses.append(f'<use href="#{gid}" x="{f(cx / k, 0)}"{extra}/>')
            cx += font.adv(ch, size) + ls
        attrs = f' fill="{fill}"' if fill else ""
        svg = (f'<g transform="translate({f(x)} {f(y)}) scale({f(k, 5)} {f(-k, 5)})"'
               f'{attrs}>{"".join(uses)}</g>')
        return svg, w

    def defs(self) -> str:
        return "".join(f'<path id="{k}" d="{v}"/>' for k, v in self.glyphs.items())


def wrap(font, text, size, maxw):
    """Greedy word wrap."""
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if font.width(trial, size) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def wrap_items(font, items, size, maxw, sep=" · "):
    """Wrap a list of phrases, breaking only between phrases where possible."""
    lines, cur = [], ""
    for item in items:
        trial = cur + sep + item if cur else item
        if font.width(trial, size) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = item
    if cur:
        lines.append(cur)
    out = []
    for line in lines:  # a single phrase that is still too long gets word-wrapped
        out += wrap(font, line, size, maxw) if font.width(line, size) > maxw else [line]
    return out


def fit(font, text, size, maxw, ls=0.0):
    """Largest size (<= size) at which text fits in maxw."""
    w = font.width(text, size, ls)
    return size if w <= maxw else size * maxw / w


# ================================================================ icons
GENERIC = {  # 24x24 icons for things without a brand logo
    "sparkle": ("fill", "M12 1.8l2.6 7.6 7.6 2.6-7.6 2.6L12 22.2l-2.6-7.6L1.8 12l7.6-2.6z"),
    "db": ("stroke", "M4 5.5c0 1.7 3.6 3 8 3s8-1.3 8-3-3.6-3-8-3-8 1.3-8 3zM4 5.5v13c0 1.7 3.6 3 8 3s8-1.3 8-3v-13M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"),
    "braces": ("stroke", "M8 3.5H7a2 2 0 0 0-2 2v4a2.5 2.5 0 0 1-2.5 2.5A2.5 2.5 0 0 1 5 14.5v4a2 2 0 0 0 2 2h1M16 3.5h1a2 2 0 0 1 2 2v4a2.5 2.5 0 0 0 2.5 2.5 2.5 2.5 0 0 0-2.5 2.5v4a2 2 0 0 1-2 2h-1"),
    "nodes": ("stroke", "M5.5 8.5a2.8 2.8 0 1 0 0-5.6 2.8 2.8 0 0 0 0 5.6zM18.5 8.5a2.8 2.8 0 1 0 0-5.6 2.8 2.8 0 0 0 0 5.6zM12 21.1a2.8 2.8 0 1 0 0-5.6 2.8 2.8 0 0 0 0 5.6zM8.3 5.7h7.4M7 8l3.6 7.7M17 8l-3.6 7.7"),
    "check": ("stroke", "M12 21.5a9.5 9.5 0 1 0 0-19 9.5 9.5 0 0 0 0 19zM7.8 12.3l2.9 2.9 5.6-6.2"),
    "globe": ("stroke", "M12 21.5a9.5 9.5 0 1 0 0-19 9.5 9.5 0 0 0 0 19zM2.5 12h19M12 2.5c2.6 2.8 3.8 6 3.8 9.5s-1.2 6.7-3.8 9.5c-2.6-2.8-3.8-6-3.8-9.5s1.2-6.7 3.8-9.5z"),
    "award": ("stroke", "M12 15.2a6.4 6.4 0 1 0 0-12.8 6.4 6.4 0 0 0 0 12.8zM8.3 14l-1.2 7.8 4.9-2.9 4.9 2.9L15.7 14"),
    "mediummark": ("fill", "M13.5 12c0 3.9-3 7-6.75 7S0 15.9 0 12s3-7 6.75-7 6.75 3.1 6.75 7zM20.9 12c0 3.6-1.5 6.6-3.4 6.6s-3.4-3-3.4-6.6 1.5-6.6 3.4-6.6 3.4 3 3.4 6.6zM24 12c0 3.3-.5 5.9-1.2 5.9s-1.2-2.6-1.2-5.9.5-5.9 1.2-5.9S24 8.7 24 12z"),
}


def brand(slug: str) -> str:
    path = HERE / "icons" / f"{slug}.svg"
    if not path.exists():
        sys.exit(f"Icon '{slug}' not found: add {path.relative_to(ROOT)} (from simpleicons.org) "
                 f"or use one of: {', '.join(GENERIC)}")
    return re.search(r'<path d="([^"]+)"', path.read_text()).group(1)


def icon(kind: str, x: float, y: float, size: float, color: str) -> str:
    """Place a 24x24 icon (brand slug or GENERIC name) at x,y."""
    tr = f'transform="translate({f(x)} {f(y)}) scale({f(size / 24, 4)})"'
    if kind in GENERIC:
        mode, d = GENERIC[kind]
        if mode == "fill":
            return f'<path {tr} fill="{color}" d="{d}"/>'
        return (f'<path {tr} fill="none" stroke="{color}" stroke-width="2" '
                f'stroke-linecap="round" stroke-linejoin="round" d="{d}"/>')
    return f'<path {tr} fill="{color}" d="{brand(kind)}"/>'


def lum(hexc: str) -> float:
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


THEMES = {
    "light": dict(card="#f6f8fa", border="#d0d7de", fg="#1f2328", muted="#59636e",
                  chip="#ffffff", chipb="#d0d7de", accent="#0969da", accent2="#8250df",
                  line="#d0d7de"),
    "dark": dict(card="#161b22", border="#30363d", fg="#e6edf3", muted="#9198a1",
                 chip="#0d1117", chipb="#30363d", accent="#4493f8", accent2="#ab7df8",
                 line="#30363d"),
}


def item_color(item: dict, t: dict, theme: str) -> str:
    """Brand colour, swapped for the text colour when it would vanish on the
    card (near-black logos in dark mode, near-white ones in light mode)."""
    if item["icon"] == "sparkle":
        return t["accent2"]
    hexc = item.get("color")
    if not hexc:
        return t["muted"]
    if theme == "dark" and lum(hexc) < 0.06:
        return t["fg"]
    if theme == "light" and lum(hexc) > 0.6:
        return t["fg"]
    return "#" + hexc


def svg_doc(w, h, body, doc, title, defs="", style=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{f(w)}" height="{f(h)}" '
            f'viewBox="0 0 {f(w)} {f(h)}" role="img" aria-label="{esc(title)}">'
            f'<title>{esc(title)}</title><style>{style}</style>'
            f'<defs>{doc.defs()}{defs}</defs>{body}</svg>')


# ================================================================ header
HEADER_STYLE = (
    ".t{animation:in .01s linear both}"
    ".f{animation:fade .6s ease-out both}"
    ".cur{animation:in .01s linear both,blink 1.1s steps(1) infinite}"
    "@keyframes in{from{opacity:0}to{opacity:1}}"
    "@keyframes fade{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}"
    "@keyframes blink{0%{opacity:1}50%{opacity:0}}"
    "@media (prefers-reduced-motion:reduce){.t,.f,.cur{animation:none}}"
)
BG, BORDER, GREEN, CMD, OUT, WHITE = "#0d1117", "#30363d", "#3fb950", "#e6edf3", "#9198a1", "#f0f6fc"
CHAR_DELAY = 0.055


def header(data: dict, narrow: bool) -> tuple[str, str]:
    d = Doc()
    W = NARROW_W if narrow else WIDE_W
    if narrow:
        P, bar, cmd_size, out_size = 22, 34, 13.5, 13
        name_size, tag_size, tag_gap = 30, 16.5, 22
        out_gap, line_gap, block_gap = 24, 19, 34
    else:
        P, bar, cmd_size, out_size = 34, 40, 15, 14
        name_size, tag_size, tag_gap = 38, 19, 25
        out_gap, line_gap, block_gap = 27, 22, 39
    maxw = W - 2 * P
    body: list[str] = []
    t = 0.35

    def cmd(text, y, start):
        p, pw = d.text(F["monob"], "$", P, y, cmd_size, fill=GREEN, delay=lambda i: start)
        c, _ = d.text(F["mono"], text, P + pw + 10 * cmd_size / 15, y, cmd_size, fill=CMD,
                      delay=lambda i: start + 0.1 + i * CHAR_DELAY)
        body.append(p + c)
        return start + 0.1 + len(text) * CHAR_DELAY

    def fade(svg, delay):
        body.append(f'<g class="f" style="animation-delay:{f(delay)}s">{svg}</g>')

    def output(lines, y, delay):
        svg = "".join(d.text(F["mono"], ln, P, y + i * line_gap, out_size, fill=OUT)[0]
                      for i, ln in enumerate(lines))
        fade(svg, delay)
        return y + (len(lines) - 1) * line_gap

    y = bar + (32 if narrow else 36)
    t = cmd("whoami", y, t)
    ns = fit(F["bold"], data["name"], name_size, maxw)
    name, _ = d.text(F["bold"], data["name"], P, y + ns * 1.27, ns, fill=WHITE, ls=-0.4 * ns / 38)
    fade(name, t + 0.15)
    y += ns * 1.27

    # Tagline in gradient: one line on desktop, split at " · " on phones.
    tags = data["tagline"].split(" · ") if narrow else [data["tagline"]]
    ts = min(fit(F["semi"], tg, tag_size, maxw) for tg in tags)
    mask, tag_w = "", 0.0
    for i, tg in enumerate(tags):
        s, w = d.text(F["semi"], tg, P, y + tag_gap + 9 + i * tag_gap * 0.95, ts, fill="#ffffff")
        mask += s
        tag_w = max(tag_w, w)
    tag_top = y + tag_gap - ts * 0.4
    y = y + tag_gap + 9 + (len(tags) - 1) * tag_gap * 0.95
    defs = (f'<mask id="tagmask" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="9999">'
            f'{mask}</mask>')
    fade(f'<rect x="{P}" y="{f(tag_top)}" width="{f(tag_w + 4)}" height="{f(y - tag_top + ts * 0.4)}" '
         f'fill="url(#grad)" mask="url(#tagmask)"/>', t + 0.35)
    t += 0.8

    y += block_gap + (6 if not narrow else 4)
    t = cmd("cat focus.txt", y, t)
    y = output(wrap_items(F["mono"], data["focus"], out_size, maxw), y + out_gap, t + 0.15)
    t += 0.55

    y += block_gap
    t = cmd("./now", y, t)
    y = output(wrap_items(F["mono"], data["now"].split(" · "), out_size, maxw), y + out_gap, t + 0.15)
    t += 0.55

    y += block_gap
    p, pw = d.text(F["monob"], "$", P, y, cmd_size, fill=GREEN, delay=lambda i: t)
    body.append(p)
    ch = cmd_size * 1.2
    body.append(f'<rect class="cur" x="{f(P + pw + 10 * cmd_size / 15)}" y="{f(y - ch * 0.78)}" '
                f'width="{f(cmd_size * 0.6)}" height="{f(ch)}" fill="{CMD}" '
                f'style="animation-delay:{f(t)}s,{f(t)}s"/>')
    H = round(y + 18)

    frame = [f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="{BG}" stroke="{BORDER}"/>',
             f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="13.5" fill="url(#dots)"/>',
             f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="13.5" fill="url(#glow)"/>',
             f'<path d="M1 {bar}h{W - 2}" stroke="{BORDER}"/>']
    r = 5 if narrow else 6
    for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        frame.append(f'<circle cx="{f(bar * 0.55 + i * r * 3.3)}" cy="{f(bar / 2 + .5)}" r="{r}" fill="{c}"/>')
    s, _ = d.text(F["mono"], "harishankar@github: ~", W / 2, bar / 2 + 4.5, 11 if narrow else 12.5,
                  anchor="middle", fill="#7d8590")
    frame.append(s)

    gx = W - (60 if narrow else 120)
    defs += ('<linearGradient id="grad" x1="0" x2="1"><stop offset="0" stop-color="#58a6ff"/>'
             '<stop offset=".55" stop-color="#a371f7"/><stop offset="1" stop-color="#f778ba"/></linearGradient>'
             f'<radialGradient id="glow" cx="{gx}" cy="40" r="{W * 0.49}" gradientUnits="userSpaceOnUse">'
             '<stop offset="0" stop-color="#a371f7" stop-opacity=".22"/>'
             '<stop offset=".45" stop-color="#58a6ff" stop-opacity=".08"/>'
             '<stop offset="1" stop-color="#58a6ff" stop-opacity="0"/></radialGradient>'
             '<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
             '<circle cx="2" cy="2" r="1" fill="#ffffff" fill-opacity=".045"/></pattern>')
    title = f"{data['name']} — {data['tagline'].replace(' · ', ', ')}"
    return svg_doc(W, H, "".join(frame + body), d, title, defs, HEADER_STYLE), title


# ================================================================ buttons
def button(link: dict) -> str:
    d = Doc()
    H = 36
    label = link["label"]
    tw = F["semi"].width(label, 13.5)
    W = round(12 + 18 + 9 + tw + 15)
    body = [f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="8" fill="#161b22" stroke="#30363d"/>']
    if link["icon"] == "linkedin":
        body.append('<rect x="12" y="9" width="18" height="18" rx="3.5" fill="#0a66c2"/>')
        body.append(d.text(F["bold"], "in", 21, 23, 12.5, anchor="middle", fill="#ffffff", ls=-0.2)[0])
    else:
        body.append(icon(link["icon"], 12, 9, 18, "#" + link.get("color", "E6EDF3")))
    body.append(d.text(F["semi"], label, 39, 23, 13.5, fill="#e6edf3")[0])
    return svg_doc(W, H, "".join(body), d, label)


def slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", label.lower())


# ================================================================ career
PULSE_STYLE = (".pulse{transform-box:fill-box;transform-origin:center;animation:p 2.4s ease-out infinite}"
               "@keyframes p{0%{transform:scale(1);opacity:.55}80%,100%{transform:scale(2.6);opacity:0}}"
               "@media (prefers-reduced-motion:reduce){.pulse{animation:none;opacity:0}}")


def current_index(jobs):
    flagged = [i for i, j in enumerate(jobs) if j.get("current")]
    return flagged[-1] if flagged else len(jobs) - 1


def dot(x, y, cur, t):
    if cur:
        return (f'<circle class="pulse" cx="{f(x)}" cy="{f(y)}" r="8" fill="{t["accent"]}"/>'
                f'<circle cx="{f(x)}" cy="{f(y)}" r="7" fill="{t["accent"]}" stroke="{t["card"]}" stroke-width="2"/>')
    return f'<circle cx="{f(x)}" cy="{f(y)}" r="6" fill="{t["card"]}" stroke="{t["accent"]}" stroke-width="2.5"/>'


def career_wide(jobs, theme):
    t, d = THEMES[theme], Doc()
    W, n = WIDE_W, len(jobs)
    cur = current_index(jobs)
    colw = (W - 40) / n
    xs = [20 + colw * (i + 0.5) for i in range(n)]
    ly = 64
    body = [f'<path d="M{f(xs[0] - 70)} {ly}H{f(xs[-1] + 70)}" stroke="{t["line"]}" stroke-width="2" stroke-linecap="round"/>',
            f'<path d="M{f(xs[0])} {ly}H{f(xs[-1])}" stroke="url(#tl)" stroke-width="2.5" stroke-linecap="round"/>']
    bottom = ly + 88
    for i, job in enumerate(jobs):
        x, is_cur = xs[i], i == cur
        body.append(d.text(F["mono"], job["years"], x, ly - 22, 12, anchor="middle",
                           fill=t["accent"] if is_cur else t["muted"])[0])
        body.append(dot(x, ly, is_cur, t))
        cs = fit(F["bold"], job["company"], 18, colw - 16)
        body.append(d.text(F["bold"], job["company"], x, ly + 44, cs, anchor="middle", fill=t["fg"], ls=-0.2)[0])
        roles = wrap(F["med"], job["role"], 13, colw - 12)
        for j, line in enumerate(roles):
            body.append(d.text(F["med"], line, x, ly + 66 + j * 17, 13, anchor="middle",
                               fill=t["accent"] if is_cur else t["accent2"])[0])
        wy = ly + 88 + (len(roles) - 1) * 17
        lines = wrap(F["reg"], job["work"], 12.5, colw - 26)
        for j, line in enumerate(lines):
            body.append(d.text(F["reg"], line, x, wy + j * 18, 12.5, anchor="middle", fill=t["muted"])[0])
        bottom = max(bottom, wy + (len(lines) - 1) * 18)
    # One bracket per run of consecutive jobs in the same country.
    by = bottom + 36
    runs: list[list[int]] = []
    for i, job in enumerate(jobs):
        if runs and jobs[runs[-1][0]]["country"] == job["country"]:
            runs[-1].append(i)
        else:
            runs.append([i])
    for run in runs:
        x1, x2 = xs[run[0]] - 60, xs[run[-1]] + 60
        body.append(f'<path d="M{f(x1)} {f(by - 6)}V{f(by)}H{f(x2)}V{f(by - 6)}" fill="none" '
                    f'stroke="{t["line"]}" stroke-width="1.5" stroke-linejoin="round"/>')
        body.append(d.text(F["semi"], jobs[run[0]]["country"].upper(), (x1 + x2) / 2, by + 22, 11,
                           anchor="middle", fill=t["muted"], ls=1.6)[0])
    H = round(by + 46)
    body.insert(0, f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="{t["card"]}" stroke="{t["border"]}"/>')
    defs = (f'<linearGradient id="tl" x1="{f(xs[0])}" x2="{f(xs[-1])}" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="{t["accent2"]}"/><stop offset="1" stop-color="{t["accent"]}"/></linearGradient>')
    return svg_doc(W, H, "".join(body), d, career_alt(jobs), defs, PULSE_STYLE)


def career_narrow(jobs, theme):
    """Vertical timeline, newest first."""
    t, d = THEMES[theme], Doc()
    W, P = NARROW_W, 20
    rail, tx = P + 10, P + 34
    cur = current_index(jobs)
    order = list(range(len(jobs)))[::-1]
    body, dots, y = [], [], P + 4
    for i in order:
        job, is_cur = jobs[i], i == cur
        body.append(d.text(F["mono"], job["years"], tx, y + 13, 13, fill=t["accent"] if is_cur else t["muted"])[0])
        body.append(d.text(F["semi"], job["country"].upper(), W - P, y + 12, 10.5, anchor="end",
                           fill=t["muted"], ls=1.4)[0])
        dots.append((y + 8.5, is_cur))
        cs = fit(F["bold"], job["company"], 19, W - P - tx)
        body.append(d.text(F["bold"], job["company"], tx, y + 39, cs, fill=t["fg"], ls=-0.2)[0])
        rs = fit(F["med"], job["role"], 14.5, W - P - tx)
        body.append(d.text(F["med"], job["role"], tx, y + 61, rs, fill=t["accent"] if is_cur else t["accent2"])[0])
        lines = wrap(F["reg"], job["work"], 14, W - P - tx)
        for j, line in enumerate(lines):
            body.append(d.text(F["reg"], line, tx, y + 82 + j * 20, 14, fill=t["muted"])[0])
        y += 82 + (len(lines) - 1) * 20 + 30
    H = round(y - 30 + P + 6)
    top, bottom = dots[0][0], dots[-1][0]
    rail_svg = (f'<path d="M{rail} {f(top)}V{f(bottom)}" stroke="url(#tl)" stroke-width="2.5" stroke-linecap="round"/>'
                + "".join(dot(rail, cy, c, t) for cy, c in dots))
    frame = f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="{t["card"]}" stroke="{t["border"]}"/>'
    defs = (f'<linearGradient id="tl" x1="0" x2="0" y1="{f(top)}" y2="{f(bottom)}" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="{t["accent"]}"/><stop offset="1" stop-color="{t["accent2"]}"/></linearGradient>')
    return svg_doc(W, H, frame + rail_svg + "".join(body), d, career_alt(jobs), defs, PULSE_STYLE)


def career_alt(jobs):
    parts = []
    for i, j in enumerate(jobs):
        years = j["years"].replace(" – now", "–present").replace(" – ", "–")
        parts.append(f"{j['company']}, {j['country']}, {years}, {j['role']}, {j['work']}")
    return "Career timeline: " + ". ".join(parts) + "."


# ================================================================ tech stack
def stack(groups, theme, narrow):
    t, d = THEMES[theme], Doc()
    if narrow:
        W, P, chip_h, gap, size, isz, sec = NARROW_W, 18, 30, 7, 14, 15, 16
        x0 = P
    else:
        W, P, chip_h, gap, size, isz, sec = WIDE_W, 24, 32, 8, 13, 16, 14
        x0 = P + 150
    maxx = W - P
    body, y = [], P
    for gi, grp in enumerate(groups):
        if gi:
            body.append(f'<path d="M{P} {f(y - sec / 2 - 0.5)}H{W - P}" stroke="{t["border"]}" stroke-opacity=".7"/>')
        if narrow:
            body.append(d.text(F["semi"], grp["group"].upper(), P, y + 11, 10.5, fill=t["muted"], ls=1.2)[0])
            y += 22
        else:
            body.append(d.text(F["semi"], grp["group"].upper(), P, y + 20, 11, fill=t["muted"], ls=1.2)[0])
        x = x0
        for item in grp["items"]:
            tw = F["med"].width(item["name"], size)
            pad = (chip_h - isz) / 2
            pad_x = pad + 2
            cw = pad_x + isz + 8 + tw + 12
            if x + cw > maxx and x > x0:
                x = x0
                y += chip_h + gap
            body.append(f'<rect x="{f(x + .5)}" y="{f(y + .5)}" width="{f(cw - 1)}" height="{chip_h - 1}" '
                        f'rx="8" fill="{t["chip"]}" stroke="{t["chipb"]}"/>')
            body.append(icon(item["icon"], x + pad_x, y + pad, isz, item_color(item, t, theme)))
            body.append(d.text(F["med"], item["name"], x + pad_x + isz + 8, y + chip_h / 2 + size * 0.36,
                               size, fill=t["fg"])[0])
            x += cw + gap
        y += chip_h + sec + 6
    H = round(y - sec - 6 + P)
    body.insert(0, f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="{t["card"]}" stroke="{t["border"]}"/>')
    return svg_doc(W, H, "".join(body), d, stack_alt(groups))


def stack_alt(groups):
    return "Tech stack. " + " ".join(
        f"{g['group']}: " + ", ".join(i["name"] for i in g["items"]) + "." for g in groups)


# ================================================================ README
def picture(name, alt):
    return (f'<picture>\n'
            f'  <source media="{NARROW} and (prefers-color-scheme: dark)" srcset="assets/{name}-narrow-dark.svg">\n'
            f'  <source media="{NARROW}" srcset="assets/{name}-narrow-light.svg">\n'
            f'  <source media="(prefers-color-scheme: dark)" srcset="assets/{name}-dark.svg">\n'
            f'  <img src="assets/{name}-light.svg" alt="{esc(alt)}">\n'
            f'</picture>')


def readme_blocks(data, header_alt):
    hdr = data["header"]
    buttons = "&nbsp;\n".join(
        f'<a href="{esc(lk["url"])}"><img src="assets/btn-{slug(lk["label"])}.svg" '
        f'alt="{esc(lk["label"])}" height="36"></a>' for lk in data["links"])
    header_block = (
        '<div align="center">\n\n'
        f'<p><a href="{esc(hdr["link"])}"><picture>\n'
        f'  <source media="{NARROW}" srcset="assets/header-narrow.svg">\n'
        f'  <img src="assets/header.svg" alt="{esc(header_alt)}">\n'
        '</picture></a></p>\n\n'
        f'{buttons}\n\n'
        '</div>')
    return {
        "header": header_block,
        "career": picture("career", career_alt(data["jobs"])),
        "stack": picture("stack", stack_alt(data["stack"])),
    }


def update_readme(text, blocks):
    for key, block in blocks.items():
        pat = re.compile(rf"(<!-- profile:{key}:start[^>]*-->).*?(<!-- profile:{key}:end -->)", re.S)
        if not pat.search(text):
            print(f"warning: README.md has no '<!-- profile:{key}:start -->' block; skipped", file=sys.stderr)
            continue
        text = pat.sub(lambda m: f"{m.group(1)}\n{block}\n{m.group(2)}", text)
    return text


# ================================================================ main
def build() -> dict[Path, str]:
    data = tomllib.loads((HERE / "profile.toml").read_text(encoding="utf-8"))
    out: dict[Path, str] = {}
    svg, header_alt = header(data["header"], narrow=False)
    out[ASSETS / "header.svg"] = svg
    out[ASSETS / "header-narrow.svg"] = header(data["header"], narrow=True)[0]
    for lk in data["links"]:
        out[ASSETS / f"btn-{slug(lk['label'])}.svg"] = button(lk)
    for theme in THEMES:
        out[ASSETS / f"career-{theme}.svg"] = career_wide(data["jobs"], theme)
        out[ASSETS / f"career-narrow-{theme}.svg"] = career_narrow(data["jobs"], theme)
        out[ASSETS / f"stack-{theme}.svg"] = stack(data["stack"], theme, narrow=False)
        out[ASSETS / f"stack-narrow-{theme}.svg"] = stack(data["stack"], theme, narrow=True)
    out[README] = update_readme(README.read_text(encoding="utf-8"), readme_blocks(data, header_alt))
    return out


def main() -> int:
    check = "--check" in sys.argv[1:]
    files = build()
    expected = set(files)
    stale = [p for p in ASSETS.glob("*.svg") if p not in expected]
    changed = [p for p, c in files.items() if not p.exists() or p.read_text(encoding="utf-8") != c]
    if check:
        for p in changed + stale:
            print(f"out of date: {p.relative_to(ROOT)}")
        return 1 if changed or stale else 0
    ASSETS.mkdir(exist_ok=True)
    for p in changed:
        p.write_text(files[p], encoding="utf-8")
        print(f"updated {p.relative_to(ROOT)}")
    for p in stale:
        p.unlink()
        print(f"removed {p.relative_to(ROOT)} (no longer used)")
    if not changed and not stale:
        print("Everything is up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
