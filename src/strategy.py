"""Strategy replay — pure backtest, no live calls, no file I/O.

Walks hourly closes, computes RSI(14) + SMA200 over the window ending at
each hour, and applies one strategy config:
  BUY  when RSI < rsi_buy and price > SMA200 (and flat)
  SELL when RSI > 70 (and holding)
  BUY allocates `alloc` of current cash; SELL exits the whole position.
Returns final value, max drawdown, trade count and the trade list.
Buy-and-hold baseline: full $10,000 in at the first close, held to the end.
"""
from analyst import rsi, sma

START_CASH = 10_000.0


def replay(closes, rsi_buy, alloc, need_trend=True):
    cash = START_CASH
    qty = 0.0
    peak = START_CASH
    max_dd = 0.0
    trades = []
    for i in range(201, len(closes)):
        window = closes[:i + 1]
        price = closes[i]
        r = rsi(window)
        s = sma(window, 200)
        if r is None or s is None:
            continue
        value = cash + qty * price
        peak = max(peak, value)
        max_dd = max(max_dd, (peak - value) / peak if peak else 0.0)
        buy_ok = r < rsi_buy and (not need_trend or price > s)
        if buy_ok and qty == 0.0 and cash > 100:
            spend = round(cash * alloc, 2)
            qty = round(spend / price, 6)
            cash = round(cash - spend, 2)
            trades.append({"i": i, "action": "BUY", "price": price,
                           "qty": qty, "spend_usd": spend})
        elif r > 70 and qty > 0.0:
            proceeds = round(qty * price, 2)
            cash = round(cash + proceeds, 2)
            trades.append({"i": i, "action": "SELL", "price": price,
                           "qty": qty, "proceeds_usd": proceeds})
            qty = 0.0
    final = round(cash + qty * closes[-1], 2)
    return {"final_value": final, "return_pct": round((final / START_CASH - 1) * 100, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "n_trades": len(trades), "trades": trades}


def buy_and_hold(closes):
    qty = START_CASH / closes[0]
    final = round(qty * closes[-1], 2)
    return {"final_value": final,
            "return_pct": round((final / START_CASH - 1) * 100, 2)}
