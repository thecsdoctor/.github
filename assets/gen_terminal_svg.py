#!/usr/bin/env python3
"""Generate assets/terminal.svg — animated terminal-style GitHub profile banner.

Content model: a Q&A-style terminal session. Each section is led by a
question-like command (whoami, whereami, what do i work on, ...) whose
output answers it. The `curl -s dany.sh` section replays the ACTUAL site
text, fetched live in CI (ANSI stripped, viewer-specific geo footer
dropped) and snapshotted to assets/danysh.txt for offline renders.

`./status --live` section: real data fetched from live sources (GitHub API,
dany.sh visitor counter, Berlin weather, latest dev.to post) plus CI
metadata (run number, sha, refresh time) when running in GitHub Actions.
Every fetch has a short timeout and silently degrades — a failed source
just drops its line. CI runs this every 8 h and commits the result
(see .github/workflows/terminal-svg.yml).
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

import pyfiglet
from xml.sax.saxutils import escape as xesc

MAXCOLS = 92  # keep every line <= this so nothing clips at 840px width
ANSI = re.compile(r"\x1b\[[0-9;]*m")
SNAPSHOT = "assets/danysh.txt"


# ---------- remote data ----------
def fetch(url, timeout=6, ua="thecsdoctor-svg/1.0"):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def fetch_json(url, timeout=4):
    return json.loads(fetch(url, timeout))


def fetch_danysh():
    """The plain-text site, exactly as `curl dany.sh` renders it."""
    raw = fetch("https://dany.sh/", timeout=8, ua="curl/8.5.0")
    txt = ANSI.sub("", raw)
    lines = [l.rstrip() for l in txt.splitlines()]
    # the geo footer is viewer-specific ("you are using curl at <CI ip> from
    # <CI location>") — meaningless inside a profile SVG, drop it
    lines = [l for l in lines if "to access this site" not in l]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    # collapse runs of blank lines to one
    out = []
    for l in lines:
        if not l.strip() and out and not out[-1].strip():
            continue
        out.append(l)
    return out


def ago(iso_ts):
    then = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    s = int((datetime.now(timezone.utc) - then).total_seconds())
    if s < 3600:
        return "%dm ago" % max(s // 60, 1)
    if s < 86400:
        return "%dh ago" % (s // 3600)
    return "%dd ago" % (s // 86400)


def trunc(s, n=MAXCOLS):
    return s if len(s) <= n else s[: n - 1] + "…"


WMO = {0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
       45: "fog", 48: "rime fog", 51: "light drizzle", 53: "drizzle",
       55: "dense drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
       66: "freezing rain", 67: "freezing rain", 71: "light snow", 73: "snow",
       75: "heavy snow", 77: "snow grains", 80: "light showers",
       81: "showers", 82: "violent showers", 85: "snow showers",
       86: "snow showers", 95: "thunderstorm", 96: "thunderstorm + hail",
       99: "thunderstorm + hail"}


def line_github():
    r = fetch_json("https://api.github.com/users/thecsdoctor/repos"
                   "?per_page=100&sort=pushed&type=owner")
    pubs = [x for x in r if not x.get("private")]
    stars = sum(x.get("stargazers_count", 0) for x in r)
    latest = r[0]
    star_s = "%d star%s" % (stars, "s" if stars != 1 else "")
    return ("github", trunc("%d public repos · %s · latest push: %s (%s)"
                            % (len(pubs), star_s, latest["name"],
                               ago(latest["pushed_at"])), MAXCOLS - 12))


def line_visitors():
    d = fetch_json("https://dany.sh/visitors")
    return ("dany.sh", "%d visitors and counting" % d["visitors"])


def line_berlin():
    d = fetch_json("https://api.open-meteo.com/v1/forecast?latitude=52.52"
                   "&longitude=13.405&current_weather=true")
    w = d["current_weather"]
    return ("berlin", "%.0f°C, %s right now" % (w["temperature"],
            WMO.get(w.get("weathercode"), "unknown sky")))


def line_devto():
    a = fetch_json("https://dev.to/api/articles?username=thecsdoctor&per_page=1")
    if not a:
        return None
    return ("dev.to", trunc('latest post: "%s"' % a[0]["title"], MAXCOLS - 12))


def line_ci():
    """Pipeline metadata — only meaningful inside GitHub Actions."""
    run = os.environ.get("GITHUB_RUN_NUMBER")
    sha = (os.environ.get("GITHUB_SHA") or "")[:7]
    if not run:
        return ("ci", "local render — the GH Action refreshes this every 8h")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    s = "refreshed %s · run #%s" % (stamp, run)
    if sha:
        s += " · " + sha
    return ("ci", s)


LIVE_FETCHERS = (line_github, line_visitors, line_berlin, line_devto, line_ci)


def live_lines(enabled):
    out = []
    if not enabled:
        return out
    for f in LIVE_FETCHERS:
        try:
            item = f()
        except Exception as e:
            print("live source %s failed: %s" % (f.__name__, e), file=sys.stderr)
            item = None
        if item:
            label, text = item
            out.append("%-10s %s" % (label, text))
    return out


def danysh_lines(live):
    if live:
        try:
            lines = fetch_danysh()
            with open(SNAPSHOT, "w") as f:
                f.write("\n".join(lines) + "\n")
            return lines
        except Exception as e:
            print("dany.sh fetch failed: %s — using snapshot" % e, file=sys.stderr)
    try:
        with open(SNAPSHOT) as f:
            return [l.rstrip("\n") for l in f]
    except OSError:
        return []


# ---------- content ----------
banner = pyfiglet.figlet_format("thecsdoctor", font="ansi_shadow", width=200)
banner_lines = [l.rstrip() for l in banner.splitlines() if l.strip()]

PROMPT = "dany@gh:~$ "


def build_transcript(site, live):
    t = [
        ("cmd", "whoami"),
        ("out", "dany"),
        ("blank", ""),
        ("cmd", "whereami"),
        ("out", "berlin, germany (wildau, to be precise)"),
        ("blank", ""),
        ("cmd", "curl -s dany.sh"),
    ]
    t += [("out", trunc(l)) if l.strip() else ("blank", "")
          for l in site]
    t += [
        ("blank", ""),
        ("cmd", "what do i work on"),
        ("out", "sr devops engineer @ accenture, berlin (2024—now) — german public sector"),
        ("out", "GenAI platform on azure A100 GPUs · n8n · MCP · vLLM · qdrant"),
        ("blank", ""),
        ("cmd", "what did i do before"),
        ("out", "devops lead @ capgemini (2022—2024) — sovereign google cloud, 20+ dev teams"),
        ("out", "software dev @ kieback&peter (2021—2022) — YOLOv4 vision testing plugin"),
        ("out", "highlights: cut AWS EC2 costs 28% · ceph SME, 8PB+ RFP · air-gapped deploys"),
        ("blank", ""),
        ("cmd", "what did i study"),
        ("out", "b.eng. telematics — TH wildau, germany (2018—2022)"),
        ("out", "certs: AWS devops pro · developer associate · cloud practitioner"),
        ("blank", ""),
        ("cmd", "where can you reach me"),
        ("out", "daniyal.ibrahim10@gmail.com · linkedin/in/daniyal-ibrahim · github/thecsdoctor"),
        ("blank", ""),
    ]
    if live:
        t.append(("cmd", "./status --live"))
        t += [("out", l) for l in live]
        t.append(("blank", ""))
    return t


# ---------- geometry ----------
W = 840
PAD = 22
TITLE_H = 36
MONO = "ui-monospace,SFMono-Regular,'DejaVu Sans Mono',Menlo,Consolas,monospace"

GREEN = "#00ff41"      # banner / bright matrix green
FG = "#3fb950"         # output green (github dark green)
DIM = "#8b949e"        # prompt gray
CMD = "#e6edf3"        # typed command near-white
BG = "#0d1117"
BAR = "#161b22"
BORDER = "#30363d"

# ---------- timing ----------
TYPE_S = 0.045        # per char
CMD_PAUSE = 0.4
OUT_GAP = 0.08
BANNER_HOLD = 0.8     # banner appears, then typing starts
END_HOLD = 180.0  # hold the finished frame ~3 min before the loop repeats


def build_svg(transcript):
    events = []  # (kind, payload, t_start, t_end)
    t = BANNER_HOLD
    for kind, text in transcript:
        if kind == "blank":
            t += 0.1
            continue
        if kind == "cmd":
            t1 = t + len(text) * TYPE_S
            events.append(("cmd", text, t, t1))
            t = t1 + CMD_PAUSE
        else:
            events.append(("out", text, t, t))
            t += OUT_GAP
    total = t + END_HOLD

    def kt(x):
        return f"{x / total:.5f}"

    banner_fs = 17
    banner_cw = banner_fs * 0.602
    banner_cols = max(len(l) for l in banner_lines)
    while banner_cols * banner_cw > W - 2 * PAD and banner_fs > 6:
        banner_fs -= 1
        banner_cw = banner_fs * 0.602
    banner_lh = banner_fs + 2

    fs = 14.5
    cw = fs * 0.602
    lh = 21

    n_rows = sum(1 for k, _ in transcript if k != "blank") + 1  # + final prompt
    H = int(TITLE_H + 14 + len(banner_lines) * banner_lh + banner_lh + n_rows * lh + 18)

    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{MONO}" role="img" aria-label="terminal: thecsdoctor — hey, i'm dany — curl https://dany.sh">
<rect width="{W}" height="{H}" rx="10" fill="{BG}" stroke="{BORDER}" stroke-width="1"/>
<rect width="{W}" height="{TITLE_H}" rx="10" fill="{BAR}"/>
<rect y="{TITLE_H - 10}" width="{W}" height="10" fill="{BAR}"/>
<circle cx="20" cy="{TITLE_H // 2}" r="6" fill="#ff5f56"/>
<circle cx="40" cy="{TITLE_H // 2}" r="6" fill="#ffbd2e"/>
<circle cx="60" cy="{TITLE_H // 2}" r="6" fill="#27c93f"/>
<text x="{W / 2}" y="{TITLE_H // 2 + 4}" font-size="12" fill="{DIM}" text-anchor="middle">dany@thecsdoctor: ~</text>
''']

    # banner (fades in)
    y = TITLE_H + 14 + banner_fs
    parts.append(f'<g fill="{GREEN}" font-size="{banner_fs}" opacity="0">')
    parts.append('<animate attributeName="opacity" from="0" to="1" begin="0s" dur="0.4s" fill="freeze" repeatCount="1" calcMode="discrete"/>')
    for i, line in enumerate(banner_lines):
        parts.append(f'<text x="{PAD}" y="{y + i * banner_lh}" xml:space="preserve">{xesc(line)}</text>')
    parts.append('</g>')

    # transcript
    y0 = y + len(banner_lines) * banner_lh + lh
    clips, texts = [], []
    yi = 0
    cursor_stops = []  # (t, x, y_rect_top) — one entry every time the cursor moves
    for idx, (kind, payload, t0, t1) in enumerate(events):
        ly = y0 + yi * lh          # text baseline
        ry = ly - fs               # cursor rect top  (was ly → off by one line)
        if kind == "cmd":
            cid = f"clip{idx}"
            x0 = PAD + len(PROMPT) * cw
            widths = [len(PROMPT) * cw] + [(len(PROMPT) + i) * cw for i in range(1, len(payload) + 1)]
            times = [t0 + i * TYPE_S for i in range(len(payload) + 1)]
            values = ";".join(f"{w:.1f}" for w in widths)
            keys = ";".join(kt(x) for x in times) + ";1"
            values += f";{widths[-1]:.1f}"
            clips.append(
                f'<clipPath id="{cid}"><rect x="{PAD}" y="{ry}" width="0" height="{lh}">'
                f'<animate attributeName="width" dur="{total:.3f}s" repeatCount="indefinite" '
                f'calcMode="discrete" keyTimes="{kt(0)};{keys}" values="0;{values}"/></rect></clipPath>'
            )
            texts.append(
                f'<text x="{PAD}" y="{ly}" font-size="{fs}" xml:space="preserve" clip-path="url(#{cid})">'
                f'<tspan fill="{DIM}">{PROMPT}</tspan><tspan fill="{CMD}">{xesc(payload)}</tspan></text>'
            )
            # cursor tracks every typed character, like a real terminal
            for i, tx in enumerate(times):
                cursor_stops.append((tx, PAD + widths[i], ry))
            yi += 1
        else:  # out line: appears at t0; cursor leads at the line start
            texts.append(
                f'<text x="{PAD}" y="{ly}" font-size="{fs}" fill="{FG}" xml:space="preserve" opacity="0">'
                f'<animate attributeName="opacity" dur="{total:.3f}s" repeatCount="indefinite" calcMode="discrete" '
                f'keyTimes="0;{kt(t0)}" values="0;1"/>{xesc(payload)}</text>'
            )
            cursor_stops.append((t0, PAD, ry))
            yi += 1

    parts.extend(clips)
    parts.extend(texts)

    # final prompt + cursor
    final_y = y0 + yi * lh
    cursor_stops.append((t, PAD + len(PROMPT) * cw, final_y - fs))
    parts.append(
        f'<text x="{PAD}" y="{final_y}" font-size="{fs}" fill="{DIM}" xml:space="preserve" opacity="0">'
        f'<animate attributeName="opacity" dur="{total:.3f}s" repeatCount="indefinite" calcMode="discrete" '
        f'keyTimes="0;{kt(t)}" values="0;1"/>{PROMPT}</text>'
    )
    xs = ";".join(f"{p[1]:.1f}" for p in cursor_stops)
    ys = ";".join(f"{p[2]:.1f}" for p in cursor_stops)
    ts_ = ";".join(kt(p[0]) for p in cursor_stops)
    parts.append(
        f'<rect width="{cw:.1f}" height="{fs + 3}" fill="{GREEN}">'
        f'<animate attributeName="x" dur="{total:.3f}s" repeatCount="indefinite" calcMode="discrete" keyTimes="0;{ts_}" values="{PAD};{xs}"/>'
        f'<animate attributeName="y" dur="{total:.3f}s" repeatCount="indefinite" calcMode="discrete" keyTimes="0;{ts_}" values="{y0 - fs};{ys}"/>'
        f'<animate attributeName="opacity" dur="0.9s" repeatCount="indefinite" calcMode="discrete" keyTimes="0;0.5" values="1;0"/>'
        f'</rect>'
    )
    parts.append('</svg>')
    return "\n".join(parts), W, H, total


def main():
    live = "--live" in sys.argv
    site = danysh_lines(live)
    lines = live_lines(live)
    transcript = build_transcript(site, lines)
    svg, w, h, total = build_svg(transcript)
    with open("assets/terminal.svg", "w") as f:
        f.write(svg)
    print(f"wrote assets/terminal.svg  {w}x{h}  cycle {total:.1f}s  "
          f"site lines: {len(site)}  live lines: {len(lines)}")


if __name__ == "__main__":
    main()
