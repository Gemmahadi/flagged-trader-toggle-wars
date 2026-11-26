"""Flagsmith flags for FlaggedTrader — reads live flags, falls back to
defaults when no key / no network, and says which mode it is in.

Flags (project `toggle-wars`, Development environment):
  trader_strategy      multivariate: conservative | balanced | aggressive
  enable_lyzr_reasoning boolean (default True)
  risk_per_trade       remote config (default 0.10)

Strategy table (RSI buy threshold + allocation per BUY):
  conservative: RSI < 25, 5% of cash
  balanced:     RSI < 30, 10% of cash
  aggressive:   RSI < 35, 20% of cash
risk_per_trade overrides the allocation when set.
"""
import os

STRATEGIES = {
    # need_trend=True = only buy the oversold dip inside an uptrend
    # (Adi's backtested rule). need_trend=False = buy the dip outright.
    "conservative": {"rsi_buy": 25, "alloc": 0.05, "need_trend": True},
    "balanced": {"rsi_buy": 30, "alloc": 0.10, "need_trend": True},
    "aggressive": {"rsi_buy": 35, "alloc": 0.20, "need_trend": False},
}

DEFAULTS = {"trader_strategy": "balanced",
            "enable_lyzr_reasoning": True,
            "risk_per_trade": 0.10}


def get_flags():
    """Returns (flags dict, mode) — mode 'flagsmith' or 'defaults'."""
    key = os.environ.get("FLAGSMITH_KEY")
    if not key:
        return dict(DEFAULTS), "defaults"
    try:
        from flagsmith import Flagsmith
        fs = Flagsmith(environment_key=key)
        flags = fs.get_environment_flags()
        strategy = flags.get_feature_value("trader_strategy") or DEFAULTS["trader_strategy"]
        if strategy not in STRATEGIES:
            strategy = DEFAULTS["trader_strategy"]
        lyzr = flags.is_feature_enabled("enable_lyzr_reasoning")
        if lyzr is None:
            lyzr = DEFAULTS["enable_lyzr_reasoning"]
        risk = flags.get_feature_value("risk_per_trade")
        try:
            risk = float(risk)
        except (TypeError, ValueError):
            risk = DEFAULTS["risk_per_trade"]
        return {"trader_strategy": strategy,
                "enable_lyzr_reasoning": bool(lyzr),
                "risk_per_trade": risk}, "flagsmith"
    except Exception:  # noqa: BLE001 - flags must never kill the demo
        return dict(DEFAULTS), "defaults"
