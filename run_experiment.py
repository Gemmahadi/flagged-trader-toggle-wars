"""FlaggedTrader experiment — replay the same 14d of real 1h closes through
all three trader_strategy variants and compare against buy-and-hold.

Usage: python3 run_experiment.py
Env:   FLAGSMITH_KEY (optional — only read to show the live flag state;
       the replay itself runs all three variants regardless).
Output: data/experiment.json + dashboard.html
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from analyst import COINS, fetch_prices  # noqa: E402
from flags import STRATEGIES, get_flags  # noqa: E402
from strategy import buy_and_hold, replay  # noqa: E402

ROOT = os.path.dirname(__file__)
DATA = os.path.join(ROOT, "data")

_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    for _line in open(_ENV):
        _line = _line.strip()
        if _line and "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v)


def main():
    live_flags, flag_mode = get_flags()
    results = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "flag_mode": flag_mode, "live_flags": live_flags,
               "coins": {}}
    for sym, coin_id in COINS.items():
        closes = fetch_prices(coin_id, days=30)
        entry = {"n_points": len(closes),
                 "first_close": closes[0], "last_close": closes[-1],
                 "buy_and_hold": buy_and_hold(closes), "variants": {}}
        for name, cfg in STRATEGIES.items():
            entry["variants"][name] = replay(
                closes, cfg["rsi_buy"], cfg["alloc"], cfg["need_trend"])
        results["coins"][sym] = entry
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "experiment.json"), "w") as f:
        json.dump(results, f, indent=2)
    rows = ""
    for sym, entry in results["coins"].items():
        bh = entry["buy_and_hold"]
        rows += (f"<tr><td>{sym}</td><td>buy-and-hold</td><td>—</td>"
                 f"<td>${bh['final_value']}</td><td>{bh['return_pct']}%</td>"
                 f"<td>—</td><td>—</td></tr>")
        for name, v in entry["variants"].items():
            trend = "+ uptrend" if STRATEGIES[name]["need_trend"] else "no filter"
            rows += (f"<tr><td>{sym}</td><td>{name}</td>"
                     f"<td>RSI&lt;{STRATEGIES[name]['rsi_buy']}, "
                     f"{int(STRATEGIES[name]['alloc'] * 100)}%, {trend}</td>"
                     f"<td>${v['final_value']}</td><td>{v['return_pct']}%</td>"
                     f"<td>{v['max_drawdown_pct']}%</td>"
                     f"<td>{v['n_trades']}</td></tr>")
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>FlaggedTrader — Toggle Wars experiment</title>
<style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:2em auto;
padding:0 1em}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px
solid #ccc;padding:.4em;text-align:left}}</style></head><body>
<h1>FlaggedTrader — which strategy wins?</h1>
<p><b>Track 02:</b> AI Agents &amp; Feature Flags (Toggle Wars, WeMakeDevs).
<b>Live flags:</b> {live_flags} (mode: {flag_mode}).
<b>Data:</b> real CoinGecko 1h closes, 30d, replayed — no live trades, no
real money. <b>Rule:</b> RSI(14) + SMA200, Adi's backtested system.
Aggressive buys the oversold dip outright; conservative/balanced only buy
it inside an uptrend.</p>
<table><tr><th>Coin</th><th>Variant</th><th>Rule</th><th>Final $</th>
<th>Return</th><th>Max drawdown</th><th>Trades</th></tr>{rows}</table>
<p><small>Generated {results['generated_utc']} UTC. FlaggedTrader by
GEMMA WORKS — hackathon demo, not financial advice.</small></p>
</body></html>"""
    with open(os.path.join(ROOT, "dashboard.html"), "w") as f:
        f.write(html)
    print(json.dumps({k: v for k, v in results.items() if k != "coins"},
                     indent=2))
    for sym, entry in results["coins"].items():
        print(sym, "buy-and-hold $", entry["buy_and_hold"]["final_value"],
              "|", {n: v["final_value"] for n, v in entry["variants"].items()})


if __name__ == "__main__":
    main()
