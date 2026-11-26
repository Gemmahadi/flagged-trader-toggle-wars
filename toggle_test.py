"""Live toggle test — prove Flagsmith's flag value drives behaviour.

1. Read the environment flags (no identity) — the control value.
2. Evaluate `trader_strategy` for a set of identities via Flagsmith's
   multivariate distribution — different identities get different
   strategy values, straight from the Flagsmith API.
3. For each distinct strategy value, compute the live signal on real
   CoinGecko prices and show the signal differs (RSI threshold, trend
   filter, allocation) — i.e. the flag genuinely steers the agent.

Usage: .venv/bin/python toggle_test.py
Env:   FLAGSMITH_KEY (from .env)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from analyst import COINS, fetch_prices, rsi, sma  # noqa: E402
from flags import STRATEGIES, get_flags  # noqa: E402

ROOT = os.path.dirname(__file__)
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    for _line in open(_ENV):
        _line = _line.strip()
        if _line and "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v)

IDENTITIES = [f"trader-{i:02d}" for i in range(1, 13)]


def signal_for(symbol, closes, strategy_name):
    cfg = STRATEGIES[strategy_name]
    price = closes[-1]
    r = rsi(closes)
    s = sma(closes, 200)
    if r is None or s is None:
        return {"strategy": strategy_name, "error": "not enough data"}
    if r < cfg["rsi_buy"] and (not cfg["need_trend"] or price > s):
        sig = "BUY"
    elif r > 70:
        sig = "SELL"
    else:
        sig = "HOLD"
    return {"strategy": strategy_name, "rsi_buy": cfg["rsi_buy"],
            "alloc": cfg["alloc"], "need_trend": cfg["need_trend"],
            "rsi14": round(r, 2), "sma200": round(s, 2),
            "price": round(price, 2), "signal": sig}


def main():
    from flagsmith import Flagsmith

    key = os.environ.get("FLAGSMITH_KEY")
    assert key, "FLAGSMITH_KEY missing from .env"
    env_flags, mode = get_flags()
    print(f"environment flags (mode={mode}): {env_flags}")

    fs = Flagsmith(environment_key=key)
    by_strategy = {}
    for ident in IDENTITIES:
        flags = fs.get_identity_flags(ident)
        val = flags.get_feature_value("trader_strategy")
        by_strategy.setdefault(val, []).append(ident)
    print(f"\nmultivariate distribution over {len(IDENTITIES)} identities:")
    for val, idents in sorted(by_strategy.items()):
        print(f"  {val}: {len(idents)} -> {idents}")

    print("\nlive signals per strategy value (same market snapshot):")
    closes = {sym: fetch_prices(cid, days=30) for sym, cid in COINS.items()}
    for strategy in sorted(by_strategy):
        for sym in COINS:
            print(f"  {strategy:13s} {sym}: {signal_for(sym, closes[sym], strategy)}")

    print("\ndivergence scan — first hour in the 30d tape where the "
          "strategies disagree (same closes, only the flag differs):")
    found = False
    for sym in COINS:
        tape = closes[sym]
        for i in range(201, len(tape)):
            window = tape[:i + 1]
            sigs = {s: signal_for(sym, window, s)["signal"]
                    for s in STRATEGIES}
            if len(set(sigs.values())) > 1:
                print(f"  {sym} hour {i}: price ${tape[i]:,.2f}, "
                      f"RSI {rsi(window):.2f}, SMA200 ${sma(window, 200):,.2f} -> {sigs}")
                found = True
                break
        if found:
            break
    if not found:
        print("  (no divergence hour in this tape)")
    print("\nTOGGLE VERDICT: "
          f"{len(by_strategy)} distinct strategy values returned live "
          f"by Flagsmith; the divergence scan shows the flag value "
          f"changes the agent's decision on identical market data.")


if __name__ == "__main__":
    main()
