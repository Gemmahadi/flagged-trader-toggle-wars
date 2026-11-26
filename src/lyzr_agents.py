"""Lyzr agent wrappers — the agents' brains.

Each DuoTrade agent is a real Lyzr Studio agent. The wrapper talks to
Lyzr's REST API directly (urllib), NOT through the lyzr-adk SDK, for two
VM-proven reasons (24 Nov 2026):
  1. lyzr-adk's httpx client crashes at init: it parses the VM's no_proxy
     list as URL patterns and chokes on the bracketed IPv6 entries
     ("Invalid port: ':1]'").
  2. The SDK's Agent.run() first GETs /v3/agents/{id}, and GETs on the
     agent-prod host hang from this VM (curl: 60 s timeout, HTTP 000),
     while POSTs to the same host answer in ~1-2 s.

Proven working from this VM (24 Nov): POST /v3/agents/ (create, needs
provider_id + model + agent_role/agent_goal/agent_instructions) and
POST /v3/inference/chat/ (agent_id, session_id, message, user_id).

Agent IDs are cached in data/lyzr_agents.json after first creation so a
demo run never creates duplicates. When LYZR_API_KEY is absent, or any
Lyzr call fails, the wrapper falls back to the deterministic local logic
and says so plainly — the demo never pretends a local computation is
an LLM.
"""
import json
import os
import urllib.error
import urllib.request
import uuid

API_BASE = "https://agent-prod.studio.lyzr.ai"
PROVIDER_ID = "openai"
MODEL = "gpt-4o-mini"
_CACHE = os.path.join(os.path.dirname(__file__), "..", "data",
                      "lyzr_agents.json")

ANALYST_INSTRUCTIONS = (
    "You are DuoTrade Analyst, a crypto market analyst agent. "
    "You receive live price indicators (RSI-14, SMA-200, price) and explain "
    "the signal in one short paragraph: what the numbers say, what the "
    "risk is, and what you recommend to the Trader agent. Be concrete, "
    "no hype, no financial advice beyond the simulated demo."
)
TRADER_INSTRUCTIONS = (
    "You are DuoTrade Trader, a paper-trading agent. You receive the "
    "Analyst agent's signal and the current virtual portfolio. You decide "
    "whether to act on the signal, in one short paragraph: your decision, "
    "the position size, and the risk check. You only ever trade simulated "
    "money. Never claim a trade is real."
)

_SPECS = {
    "analyst": {
        "name": "DuoTradeAnalyst",
        "agent_role": "Crypto market analyst",
        "agent_goal": "Explain live market signals to the Trader agent in one short paragraph.",
        "agent_instructions": ANALYST_INSTRUCTIONS,
    },
    "trader": {
        "name": "DuoTradeTrader",
        "agent_role": "Paper-trading agent",
        "agent_goal": "Decide whether to act on the Analyst signal in one short paragraph.",
        "agent_instructions": TRADER_INSTRUCTIONS,
    },
}


def _key():
    return os.environ.get("LYZR_API_KEY")


def _post(path, payload):
    """One POST to the Lyzr API with a single retry (egress proxy stalls)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        API_BASE + path, data=data,
        headers={"x-api-key": _key(), "Content-Type": "application/json"},
        method="POST")
    last = None
    for _ in range(2):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def _agent_ids():
    """Return {'analyst': id, 'trader': id}, creating agents on first use."""
    if os.path.exists(_CACHE):
        with open(_CACHE) as f:
            cached = json.load(f)
        if all(k in cached for k in ("analyst", "trader")):
            return cached
    ids = {}
    for role, spec in _SPECS.items():
        body = {"name": spec["name"], "provider_id": PROVIDER_ID,
                "model": MODEL, "agent_role": spec["agent_role"],
                "agent_goal": spec["agent_goal"],
                "agent_instructions": spec["agent_instructions"],
                "temperature": 0.7, "top_p": 0.9,
                "llm_credential_id": "lyzr_openai"}
        resp = _post("/v3/agents/", body)
        ids[role] = resp["agent_id"]
    os.makedirs(os.path.dirname(_CACHE), exist_ok=True)
    with open(_CACHE, "w") as f:
        json.dump(ids, f)
    return ids


def _ask(role, prompt):
    """Ask a Lyzr agent; returns (text, mode). mode is 'lyzr' or 'local'."""
    if not _key():
        return None, "local"
    try:
        agent_id = _agent_ids()[role]
        resp = _post("/v3/inference/chat/", {
            "agent_id": agent_id,
            "session_id": f"duotrade-{uuid.uuid4().hex[:8]}",
            "message": prompt,
            "user_id": "duotrade-demo",
        })
        text = (resp or {}).get("response") or ""
        if not text.strip():
            return None, "local"
        return text.strip(), "lyzr"
    except Exception:  # noqa: BLE001 - any Lyzr failure -> labelled fallback
        return None, "local"


def analyst_reason(signal):
    prompt = (f"Market snapshot for {signal['symbol']}: price "
              f"${signal['price_usd']}, RSI-14 {signal['rsi14']}, SMA-200 "
              f"${signal['sma200']}. Computed signal: {signal['signal']} "
              f"because {signal['reason']}. Explain this to the Trader.")
    text, mode = _ask("analyst", prompt)
    if mode == "local":
        return (f"[local] {signal['symbol']}: {signal['signal']} — "
                f"{signal['reason']} (RSI {signal['rsi14']}, "
                f"SMA200 ${signal['sma200']})."), mode
    return text, mode


def trader_reason(signal, trade, portfolio_value):
    prompt = (f"Analyst signal for {signal['symbol']}: {signal['signal']} "
              f"at ${signal['price_usd']}. Trade executed: {trade['action']} "
              f"{trade.get('qty', '')} ({trade.get('note', '')}). Virtual "
              f"portfolio value now ${portfolio_value}. Justify the "
              f"decision in one paragraph.")
    text, mode = _ask("trader", prompt)
    if mode == "local":
        return (f"[local] Trader {trade['action']} {signal['symbol']} "
                f"per signal {signal['signal']}; portfolio "
                f"${portfolio_value} (simulated)."), mode
    return text, mode
