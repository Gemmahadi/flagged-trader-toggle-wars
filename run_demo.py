"""FlaggedTrader live run — Analyst -> Band room -> Trader -> dashboard,
with the Trader's behaviour read live from Flagsmith flags.

One run: live CoinGecko prices, signal from the flag's strategy
(RSI threshold + trend filter), Lyzr reasoning when the flag is on
(local labelled fallback when off or when Lyzr fails), Band room handoff,
simulated paper trades, static HTML dashboard.

Usage:  python3 run_demo.py
Env:    FLAGSMITH_KEY, LYZR_API_KEY, BAND_* (see .env.example)
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from analyst import COINS, fetch_prices, rsi, sma  # noqa: E402
from band_client import post  # noqa: E402
from flags import STRATEGIES, get_flags  # noqa: E402
from lyzr_agents import analyst_reason, trader_reason  # noqa: E402

ROOT = os.path.dirname(__file__)
DATA = os.path.join(ROOT, "data")
START_CASH = 10_000.0

_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    for _line in open(_ENV):
        _line = _line.strip()
        if _line and "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v)

ANALYST_HANDLE = "gemmahadi/duotrade-analyst"
TRADER_HANDLE = "gemmahadi/duotrade-trader"


def load_portfolio():
    p = os.path.join(DATA, "portfolio.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"cash": START_CASH, "positions": {}}


def save_portfolio(pf):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "portfolio.json"), "w") as f:
        json.dump(pf, f, indent=2)


def analyze_with_strategy(symbol, rsi_buy, need_trend):
    closes = fetch_prices(COINS[symbol])
    price = closes[-1]
    r = rsi(closes)
    s = sma(closes, 200)
    if r is None or s is None:
        return {"symbol": symbol, "error": "not enough data"}
    if r < rsi_buy and (not need_trend or price > s):
        signal, why = "BUY", f"oversold (RSI<{rsi_buy})" + (" + price above SMA200 uptrend" if need_trend else " (dip, no trend filter)")
    elif r > 70:
        signal, why = "SELL", "overbought (RSI>70)"
    else:
        signal, why = "HOLD", "no edge: RSI in neutral band"
    return {"symbol": symbol, "price_usd": round(price, 2),
            "rsi14": round(r, 2), "sma200": round(s, 2),
            "signal": signal, "reason": why,
            "n_points": len(closes), "timeframe": "1h closes, CoinGecko, 30d"}


def execute(pf, signal, alloc):
    sym = signal["symbol"]
    price = signal["price_usd"]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rec = {"time": now, "symbol": sym, "signal": signal["signal"],
           "price": price, "action": "NONE", "note": signal.get("reason", "")}
    pos = pf["positions"].get(sym, 0.0)
    if signal["signal"] == "BUY" and pos == 0.0 and pf["cash"] > 100:
        spend = round(pf["cash"] * alloc, 2)
        qty = round(spend / price, 6)
        pf["cash"] = round(pf["cash"] - spend, 2)
        pf["positions"][sym] = qty
        rec.update(action="BUY", qty=qty, spend_usd=spend)
    elif signal["signal"] == "SELL" and pos > 0.0:
        proceeds = round(pos * price, 2)
        pf["cash"] = round(pf["cash"] + proceeds, 2)
        pf["positions"][sym] = 0.0
        rec.update(action="SELL", qty=pos, proceeds_usd=proceeds)
    else:
        rec["note"] += " | trader: no position change"
    trades_p = os.path.join(DATA, "trades.json")
    trades = json.load(open(trades_p)) if os.path.exists(trades_p) else []
    trades.append(rec)
    os.makedirs(DATA, exist_ok=True)
    with open(trades_p, "w") as f:
        json.dump(trades, f, indent=2)
    return rec


def main():
    flags, flag_mode = get_flags()
    cfg = STRATEGIES[flags["trader_strategy"]]
    alloc = flags["risk_per_trade"] or cfg["alloc"]
    room = os.environ.get("BAND_ROOM_ID")
    a_key = os.environ.get("BAND_ANALYST_API_KEY")
    t_key = os.environ.get("BAND_TRADER_API_KEY")
    pf = load_portfolio()
    signals, trades = [], []
    lyzr_mode, band_mode = "local", "local-transcript"
    for sym in COINS:
        try:
            sig = analyze_with_strategy(sym, cfg["rsi_buy"], cfg["need_trend"])
        except Exception as e:  # noqa: BLE001
            sig = {"symbol": sym, "error": str(e)}
            signals.append(sig)
            continue
        signals.append(sig)
        if flags["enable_lyzr_reasoning"]:
            reason, lyzr_mode = analyst_reason(sig)
        else:
            reason, lyzr_mode = (f"[local] {sig['symbol']}: {sig['signal']} — "
                                 f"{sig['reason']} (flag: lyzr off)"), "local"
        r = post("DuoTrade Analyst", a_key, room,
                 f"@{TRADER_HANDLE} {sig['symbol']} signal "
                 f"{sig['signal']} at ${sig['price_usd']}: {reason} "
                 f"[strategy={flags['trader_strategy']}]",
                 mention_id=os.environ.get("BAND_TRADER_AGENT_ID"),
                 mention_handle=TRADER_HANDLE)
        band_mode = r["mode"]
        trade = execute(pf, sig, alloc)
        trades.append(trade)
        save_portfolio(pf)
        prices = {s["symbol"]: s.get("price_usd", 0) for s in signals}
        value = round(pf["cash"] + sum(
            q * prices.get(s, 0) for s, q in pf["positions"].items()), 2)
        if flags["enable_lyzr_reasoning"]:
            treason, _ = trader_reason(sig, trade, value)
        else:
            treason = (f"[local] Trader {trade['action']} {sig['symbol']} "
                       f"per signal {sig['signal']}; portfolio ${value} "
                       f"(simulated, flag: lyzr off)")
        post("DuoTrade Trader", t_key, room,
             f"@{ANALYST_HANDLE} {sig['symbol']}: {treason}",
             mention_id=os.environ.get("BAND_ANALYST_AGENT_ID"),
             mention_handle=ANALYST_HANDLE)
    prices = {s["symbol"]: s.get("price_usd", 0) for s in signals}
    value = round(pf["cash"] + sum(
        q * prices.get(s, 0) for s, q in pf["positions"].items()), 2)
    print(json.dumps({"flags": flags, "flag_mode": flag_mode,
                      "signals": signals, "trades": trades,
                      "portfolio_value": value, "lyzr": lyzr_mode,
                      "band": band_mode}, indent=2))


if __name__ == "__main__":
    main()
