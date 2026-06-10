"""Fake claude binary for offline tests (invoked as: python fake_claude.py ...).

Behavior selected via FAKE_CLAUDE_MODE:
  ok                 -> valid TripwireSet JSON in result
  judge_ok           -> valid JudgeVerdict JSON in result
  malformed_always   -> prose (schema-invalid) result every call
  malformed_then_ok  -> schema-invalid on the first call, valid afterwards
                        (call count persisted in the file at FAKE_CLAUDE_COUNTER)
  zero_cost          -> valid set but total_cost_usd == 0 (reconstruction path)
  sleep              -> hangs 30s (timeout/tree-kill path)
  throttle           -> exit 1 with rate-limit stderr (M5 queue path)
"""
import json
import os
import sys
import time
from pathlib import Path

VALID_TRIPWIRE_SET = {
    "plan_id": "a1",
    "tripwires": [
        {
            "id": "tw_pricing_endpoint_404",
            "severity": "CRITICAL",
            "scope": "global",
            "assumption": "GET /pricing/quote/{sku} exists and returns 200 with a unit_price field.",
            "assumption_id": "a1",
            "category_weights": {"API_SURFACE": 1.0},
            "signal": {
                "type": "http_response",
                "method": "GET",
                "url_pattern": "/pricing/quote/*",
                "status_in": [404, 410],
            },
            "action": {
                "on_trigger": "PAUSE_AND_REPLAN",
                "hint": "Replace pricing-quote calls with a supported endpoint and redispatch step s3.",
            },
            "evidence_fields": ["status", "path"],
        }
    ],
}

VALID_VERDICT = {
    "verdict": "GENUINE",
    "confidence": 0.9,
    "scope_confirmed": "global",
    "affected_subplans": ["s3"],
    "replan_hint": "Switch step s3 to the supported pricing endpoint and redispatch.",
    "reason": "404 with deprecation body directly violates the monitored assumption.",
}


def payload(result_text: str, cost: float = 0.01) -> dict:
    return {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": result_text,
        "session_id": "fake-session-123",
        "num_turns": 1,
        "total_cost_usd": cost,
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 200,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation": {"ephemeral_5m_input_tokens": 0,
                               "ephemeral_1h_input_tokens": 0},
        },
        "modelUsage": {},
    }


def main() -> int:
    sys.stdin.read()
    mode = os.environ.get("FAKE_CLAUDE_MODE", "ok")

    if mode == "sleep":
        time.sleep(30)
        return 0
    if mode == "throttle":
        print("Error: rate limit exceeded; retry after the window rolls (429)",
              file=sys.stderr)
        return 1
    if mode == "malformed_then_ok":
        counter_file = Path(os.environ["FAKE_CLAUDE_COUNTER"])
        n = int(counter_file.read_text()) if counter_file.exists() else 0
        counter_file.write_text(str(n + 1))
        mode = "malformed_always" if n == 0 else "ok"

    if mode == "malformed_always":
        out = payload("Here are your tripwires! I hope they help.")
    elif mode == "judge_ok":
        out = payload(json.dumps(VALID_VERDICT))
    elif mode == "zero_cost":
        out = payload(json.dumps(VALID_TRIPWIRE_SET), cost=0.0)
    else:  # ok
        out = payload(json.dumps(VALID_TRIPWIRE_SET))

    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
