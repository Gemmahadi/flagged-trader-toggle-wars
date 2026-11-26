"""Band client — the agent-to-agent coordination layer.

Agents talk in a shared Band room (REST per docs.band.ai). This client
posts messages to the room; when Band credentials are absent (not yet
registered / offline test), it mirrors the message to the local room
transcript (data/band_transcript.md) so the pipeline still runs and the
handoff stays visible and auditable.

Note: python `requests` stalls on app.band.ai in this VM (read timeouts)
while curl/urllib work fine — so this client uses urllib.
"""
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = "https://app.band.ai/api/v1/agent"
DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def _transcript(agent, text):
    os.makedirs(DATA, exist_ok=True)
    line = (f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] "
            f"@{agent}: {text}\n")
    with open(os.path.join(DATA, "band_transcript.md"), "a") as f:
        f.write(line)
    return {"mode": "local-transcript", "agent": agent, "text": text}


def _call(method, path, api_key, payload=None):
    url = f"{BASE}{path}"
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "X-API-Key": api_key,
        "Content-Type": "application/json",
        "User-Agent": "DuoTrade/0.1",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, json.load(r)


def post(agent_name, api_key, room_id, text, mention_id=None,
         mention_handle=None):
    """Post a text message to a Band room. Returns a status dict.

    The Agent API wraps the message in {"message": {...}} and REQUIRES at
    least one @mention for routing, so callers pass the other agent's id
    and handle (both are public identifiers, not secrets).
    """
    if not api_key or not room_id:
        return _transcript(agent_name, text)
    mentions = ([{"id": mention_id, "handle": mention_handle}]
                if mention_id and mention_handle else [])
    last_exc = None
    for _attempt in range(2):  # one retry: the first call after idle often
        try:                   # stalls on the egress proxy and times out
            status, body = _call("POST", f"/chats/{room_id}/messages",
                                 api_key, {"message": {"content": text,
                                                       "mentions": mentions}})
            # Mirror every posted message to the local transcript too, so
            # the dashboard always shows the real room exchange (the file
            # is a log of what went to Band, not only a failure fallback).
            _transcript(agent_name, text)
            return {"mode": "band", "agent": agent_name, "status": status,
                    "body": body}
        except urllib.error.HTTPError as e:
            _transcript(agent_name, f"[Band HTTP {e.code}] {text}")
            return {"mode": "band-failed", "agent": agent_name,
                    "status": e.code,
                    "body": e.read()[:300].decode(errors="replace")}
        except Exception as e:  # noqa: BLE001
            last_exc = e
    _transcript(agent_name, f"[Band error: {last_exc}] {text}")
    return {"mode": "band-error", "agent": agent_name, "error": str(last_exc)}


def whoami(api_key):
    if not api_key:
        return None
    try:
        status, body = _call("GET", "/me", api_key)
        return body if status == 200 else None
    except Exception:  # noqa: BLE001
        return None
