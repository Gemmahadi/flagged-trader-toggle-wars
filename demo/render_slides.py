"""Render FlaggedTrader demo-video slides (1280x720 PNGs) from the REAL
experiment output (data/experiment.json) and the REAL live flag state.

Slides: title -> experiment results -> architecture -> live flags -> closing.
Re-render at kickoff with fresh data; this file + the ffmpeg assembly are
verified working before the hack window opens.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ROOT = "/home/hatch/workspace/prize-runs/toggle-wars/flagged-trader"
DEMO = os.path.join(ROOT, "demo")
W, H = 1280, 720

SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

ACCENT = (255, 176, 32)


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, fnt, width):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def card(bg, title, subtitle=None):
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 10], fill=ACCENT)
    d.rectangle([0, H - 10, W, H], fill=ACCENT)
    d.text((80, 90), title, font=font(SANS_B, 64), fill=(255, 255, 255))
    if subtitle:
        y = 190
        for line in wrap(d, subtitle, font(SANS, 30), W - 160):
            d.text((80, y), line, font=font(SANS, 30), fill=(200, 205, 215))
            y += 44
    return im, d


exp = json.load(open(os.path.join(ROOT, "data", "experiment.json")))

# --- 1. Title ------------------------------------------------------------
im, d = card((13, 17, 23), "FlaggedTrader",
             "The trading agent whose strategy is decided by feature flags.")
d.text((80, 330), "Analyst Agent  +  Trader Agent  +  Flagsmith",
       font=font(SANS_B, 38), fill=ACCENT)
d.text((80, 400), "Live crypto prices  •  RSI(14) + SMA200  •  Real A/B experiment",
       font=font(SANS, 28), fill=(200, 205, 215))
d.text((80, 470), "Toggle Wars  •  Track 02: AI Agents & Feature Flags  •  WeMakeDevs",
       font=font(SANS, 28), fill=(140, 150, 165))
im.save(f"{DEMO}/slide-title.png")

# --- 2. Experiment: real 30d replay numbers ------------------------------
im = Image.new("RGB", (W, H), (11, 14, 20))
d = ImageDraw.Draw(im)
d.rectangle([0, 0, W, 64], fill=(30, 34, 44))
d.text((24, 16), "Experiment — same 30 days of real 1h closes, every variant",
       font=font(SANS_B, 26), fill=(230, 235, 245))
y = 92
d.text((24, y), "Coin      Variant         Final $      Return    Trades",
       font=font(MONO, 24), fill=(255, 176, 32))
y += 44
for sym, entry in exp["coins"].items():
    bh = entry["buy_and_hold"]
    rows = [("buy-and-hold", bh["final_value"], bh["return_pct"], "—")]
    for name, v in entry["variants"].items():
        rows.append((name, v["final_value"], v["return_pct"], v["n_trades"]))
    for name, val, ret, n in rows:
        best = name != "buy-and-hold" and val == max(
            r[1] for r in rows)
        col = (120, 220, 140) if best else (215, 220, 230)
        d.text((24, y), f"{sym:<8} {name:<14} ${val:<10} {ret:>6}%   {n}",
               font=font(MONO, 24), fill=col)
        y += 40
    y += 12
d.text((24, H - 56), "Real numbers — the flags decide the strategy, the tape picks the winner.",
       font=font(SANS, 24), fill=(140, 150, 165))
im.save(f"{DEMO}/slide-experiment.png")

# --- 3. Architecture ------------------------------------------------------
im = Image.new("RGB", (W, H), (13, 17, 23))
d = ImageDraw.Draw(im)
d.rectangle([0, 0, W, 10], fill=ACCENT)
d.text((80, 50), "How it works", font=font(SANS_B, 56), fill=(255, 255, 255))
boxes = [
    ("CoinGecko\n(live prices)", (40, 200, 300, 340)),
    ("Analyst Agent\nRSI + SMA200", (330, 200, 590, 340)),
    ("Flagsmith\nstrategy flags", (620, 200, 880, 340)),
    ("Trader Agent\npaper trades", (910, 200, 1240, 340)),
]
for label, (x0, y0, x1, y1) in boxes:
    d.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=(30, 36, 48),
                        outline=ACCENT, width=2)
    yy = y0 + 34
    for ln in label.split("\n"):
        d.text((x0 + 14, yy), ln, font=font(SANS_B, 22), fill=(235, 240, 248))
        yy += 32
for x in (300, 590, 880):
    d.text((x + 4, 252), "→", font=font(SANS_B, 30), fill=ACCENT)
d.text((80, 420), "One market snapshot, three flag values — the experiment runs all of them.",
       font=font(SANS, 26), fill=(200, 205, 215))
d.text((80, 480), "Flip a flag in the Flagsmith dashboard and the agent behaves differently.",
       font=font(SANS, 26), fill=(200, 205, 215))
d.text((80, 540), "Portfolio: $10,000 virtual  •  NO real money",
       font=font(SANS, 24), fill=(160, 168, 180))
im.save(f"{DEMO}/slide-arch.png")

# --- 4. Live flags --------------------------------------------------------
lf = exp["live_flags"]
im, d = card((13, 17, 23), "Live flags right now",
             f"Read from Flagsmith just now (mode: {exp['flag_mode']}). "
             "Change them in the dashboard — no redeploy, the agent follows.")
y = 330
for name, val in lf.items():
    d.text((80, y), f"{name}", font=font(SANS_B, 30), fill=ACCENT)
    d.text((560, y), f"{val}", font=font(MONO, 30), fill=(235, 240, 248))
    y += 56
im.save(f"{DEMO}/slide-flags.png")

# --- 5. Closing -----------------------------------------------------------
im, d = card((13, 17, 23), "Try it yourself",
             "Clone the repo, add your Flagsmith + Lyzr + Band keys to .env, "
             "run python3 run_experiment.py — then flip a flag and watch the "
             "agent change its mind.")
d.text((80, 430), "FlaggedTrader  •  Toggle Wars  •  Track 02",
       font=font(SANS_B, 30), fill=ACCENT)
d.text((80, 490), "Flagsmith  •  Lyzr agents  •  Live prices  •  Paper trades",
       font=font(SANS, 26), fill=(200, 205, 215))
im.save(f"{DEMO}/slide-closing.png")

print("slides done:", sorted(os.listdir(DEMO)))
