#!/usr/bin/env python3
"""Generate assets/terminal.svg — animated terminal-style GitHub profile banner."""
import pyfiglet
from xml.sax.saxutils import escape as xesc

# ---------- content ----------
banner = pyfiglet.figlet_format("thecsdoctor", font="ansi_shadow", width=200)
banner_lines = [l.rstrip() for l in banner.splitlines() if l.strip()]

PROMPT = "dany@gh:~$ "
transcript = [
    ("cmd", "whoami"),
    ("out", "dany"),
    ("blank", ""),
    ("cmd", "curl -s https://dany.sh"),
    ("out", "Daniyal Ibrahim — DevOps engineer & consultant, Berlin"),
    ("out", "software developer by profession — still one by passion"),
    ("out", "AWS certified: DevOps Pro · Developer Associate · Cloud Practitioner"),
    ("out", "github   https://github.com/thecsdoctor"),
    ("out", "web      https://dany.sh   (try: curl https://dany.sh)"),
    ("blank", ""),
]

# ---------- geometry ----------
W = 840
PAD = 22
TITLE_H = 36
MONO = "ui-monospace,SFMono-Regular,'DejaVu Sans Mono',Menlo,Consolas,monospace"

BANNER_FS = 17
BANNER_CW = BANNER_FS * 0.602
banner_cols = max(len(l) for l in banner_lines)
# shrink banner font if it would overflow
while banner_cols * BANNER_CW > W - 2 * PAD and BANNER_FS > 6:
    BANNER_FS -= 1
    BANNER_CW = BANNER_FS * 0.602
BANNER_LH = BANNER_FS + 2

FS = 14.5
CW = FS * 0.602
LH = 21

GREEN = "#00ff41"      # banner / bright matrix green
FG = "#3fb950"         # output green (github dark green)
DIM = "#8b949e"        # prompt gray
CMD = "#e6edf3"        # typed command near-white
BG = "#0d1117"
BAR = "#161b22"
BORDER = "#30363d"

# ---------- timing ----------
TYPE_S = 0.055        # per char
CMD_PAUSE = 0.45
OUT_GAP = 0.13
BANNER_HOLD = 0.8     # banner appears, then typing starts
END_HOLD = 4.0

events = []  # (kind, payload, t_start, t_end)
t = BANNER_HOLD
for kind, text in transcript:
    if kind == "blank":
        t += 0.12
        continue
    if kind == "cmd":
        n = len(text)
        t1 = t + n * TYPE_S
        events.append(("cmd", text, t, t1))
        t = t1 + CMD_PAUSE
    else:
        events.append(("out", text, t, t))
        t += OUT_GAP
TOTAL = t + END_HOLD

def kt(x):
    return f"{x / TOTAL:.4f}"

# ---------- svg build ----------
n_lines = len(banner_lines) + 1 + sum(1 for k, _ in transcript)  # +1 gap after banner
H = int(TITLE_H + 14 + len(banner_lines) * BANNER_LH + BANNER_LH + sum(1 for k, _ in transcript) * LH + 18)

parts = []
parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{MONO}" role="img" aria-label="terminal: thecsdoctor — hey, i'm dany — curl https://dany.sh">
<rect width="{W}" height="{H}" rx="10" fill="{BG}" stroke="{BORDER}" stroke-width="1"/>
<rect width="{W}" height="{TITLE_H}" rx="10" fill="{BAR}"/>
<rect y="{TITLE_H - 10}" width="{W}" height="10" fill="{BAR}"/>
<circle cx="20" cy="{TITLE_H // 2}" r="6" fill="#ff5f56"/>
<circle cx="40" cy="{TITLE_H // 2}" r="6" fill="#ffbd2e"/>
<circle cx="60" cy="{TITLE_H // 2}" r="6" fill="#27c93f"/>
<text x="{W / 2}" y="{TITLE_H // 2 + 4}" font-size="12" fill="{DIM}" text-anchor="middle">dany@thecsdoctor: ~</text>
''')

# banner (fades in)
y = TITLE_H + 14 + BANNER_FS
parts.append(f'<g fill="{GREEN}" font-size="{BANNER_FS}" opacity="0">')
parts.append(f'<animate attributeName="opacity" from="0" to="1" begin="0s" dur="0.4s" fill="freeze" repeatCount="1" calcMode="discrete"/>')
for i, line in enumerate(banner_lines):
    parts.append(f'<text x="{PAD}" y="{y + i * BANNER_LH}" xml:space="preserve">{xesc(line)}</text>')
parts.append('</g>')

# transcript
y0 = y + len(banner_lines) * BANNER_LH + LH
clips = []
texts = []
yi = 0
cursor_stops = []  # (t, x, y) positions where the cursor rests
for idx, (kind, payload, t0, t1) in enumerate(events):
    ly = y0 + yi * LH
    if kind == "cmd":
        full = PROMPT + payload
        cid = f"clip{idx}"
        # clip rect: starts at prompt width, grows char by char
        x0 = PAD + len(PROMPT) * CW
        widths = [len(PROMPT) * CW] + [(len(PROMPT) + i) * CW for i in range(1, len(payload) + 1)]
        times = [t0 + i * TYPE_S for i in range(len(payload) + 1)]
        values = ";".join(f"{w:.1f}" for w in widths)
        keys = ";".join(kt(x) for x in times) + ";1"
        values += f";{widths[-1]:.1f}"
        clips.append(
            f'<clipPath id="{cid}"><rect x="{PAD}" y="{ly - FS}" width="0" height="{LH}">'
            f'<animate attributeName="width" dur="{TOTAL:.3f}s" repeatCount="indefinite" '
            f'calcMode="discrete" keyTimes="{kt(0)};{keys}" values="0;{values}"/></rect></clipPath>'
        )
        texts.append(
            f'<text x="{PAD}" y="{ly}" font-size="{FS}" xml:space="preserve" clip-path="url(#{cid})">'
            f'<tspan fill="{DIM}">{PROMPT}</tspan><tspan fill="{CMD}">{xesc(payload)}</tspan></text>'
        )
        cursor_stops.append((t0, x0, ly))
        cursor_stops.append((t1, x0 + len(payload) * CW, ly))
        yi += 1
    else:  # out line: appears at t0
        texts.append(
            f'<text x="{PAD}" y="{ly}" font-size="{FS}" fill="{FG}" xml:space="preserve" opacity="0">'
            f'<animate attributeName="opacity" dur="{TOTAL:.3f}s" repeatCount="indefinite" calcMode="discrete" '
            f'keyTimes="0;{kt(t0)}" values="0;1"/>{xesc(payload)}</text>'
        )
        cursor_stops.append((t0, PAD, ly))
        yi += 1

parts.extend(clips)
parts.extend(texts)

# cursor: jumps between rest stops, blinks while resting
final_y = y0 + yi * LH
cursor_stops.append((t, PAD + len(PROMPT) * CW, final_y))
# final prompt line itself
parts.append(
    f'<text x="{PAD}" y="{final_y}" font-size="{FS}" fill="{DIM}" xml:space="preserve" opacity="0">'
    f'<animate attributeName="opacity" dur="{TOTAL:.3f}s" repeatCount="indefinite" calcMode="discrete" '
    f'keyTimes="0;{kt(t)}" values="0;1"/>{PROMPT}</text>'
)
xs = ";".join(f"{p[1]:.1f}" for p in cursor_stops)
ys = ";".join(f"{p[2]:.1f}" for p in cursor_stops)
ts_ = ";".join(kt(p[0]) for p in cursor_stops)
parts.append(
    f'<rect width="{CW:.1f}" height="{FS + 3}" fill="{GREEN}">'
    f'<animate attributeName="x" dur="{TOTAL:.3f}s" repeatCount="indefinite" calcMode="discrete" keyTimes="0;{ts_}" values="{PAD};{xs}"/>'
    f'<animate attributeName="y" dur="{TOTAL:.3f}s" repeatCount="indefinite" calcMode="discrete" keyTimes="0;{ts_}" values="{y0 - FS};{ys}"/>'
    f'<animate attributeName="opacity" dur="0.9s" repeatCount="indefinite" calcMode="discrete" keyTimes="0;0.5" values="1;0"/>'
    f'</rect>'
)
parts.append('</svg>')

svg = "\n".join(parts)
with open("assets/terminal.svg", "w") as f:
    f.write(svg)
print(f"wrote assets/terminal.svg  {W}x{H}  cycle {TOTAL:.1f}s  banner font {BANNER_FS}px")
