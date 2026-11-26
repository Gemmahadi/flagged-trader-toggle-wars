"""DuoTrade Analyst — live market data (CoinGecko, free, no key) + RSI/SMA signal.

Backtested rule (Adi's system, 17 Nov 2026, ETH/BTC 4h): RSI(14) < 30 AND
price > SMA200 -> long. Here applied on hourly closes (CoinGecko
market_chart, 14 days ~ 336 points) because Binance klines are geo-blocked
in this VM. The rule shape is identical; the timeframe is stated honestly.
"""
import json
import os
import sys
import urllib.request

COINS = {"ETH": "ethereum", "BTC": "bitcoin"}
DAYS = 14


def fetch_prices(coin_id, days=DAYS):
    url = (f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
           f"?vs_currency=usd&days={days}")
    req = urllib.request.Request(url, headers={"User-Agent": "DuoTrade/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    closes = [p[1] for p in data["prices"]]
    return closes


def sma(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def rsi(closes, n=14):
    """Wilder's RSI."""
    if len(closes) < n + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[:n]) / n
    avg_loss = sum(losses[:n]) / n
    for g, l in zip(gains[n:], losses[n:]):
        avg_gain = (avg_gain * (n - 1) + g) / n
        avg_loss = (avg_loss * (n - 1) + l) / n
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def analyze(symbol):
    closes = fetch_prices(COINS[symbol])
    price = closes[-1]
    r = rsi(closes)
    s = sma(closes, 200)
    if r is None or s is None:
        return {"symbol": symbol, "error": "not enough data"}
    if r < 30 and price > s:
        signal, why = "BUY", "oversold (RSI<30) + price above SMA200 uptrend"
    elif r > 70:
        signal, why = "SELL", "overbought (RSI>70)"
    else:
        signal, why = "HOLD", "no edge: RSI in neutral band"
    return {
        "symbol": symbol,
        "price_usd": round(price, 2),
        "rsi14": round(r, 2),
        "sma200": round(s, 2),
        "signal": signal,
        "reason": why,
        "n_points": len(closes),
        "timeframe": "1h closes, CoinGecko, 14d",
    }


if __name__ == "__main__":
    out = {}
    for sym in COINS:
        try:
            out[sym] = analyze(sym)
        except Exception as e:  # noqa: BLE001 - demo must not die on one coin
            out[sym] = {"symbol": sym, "error": str(e)}
    print(json.dumps(out, indent=2))
