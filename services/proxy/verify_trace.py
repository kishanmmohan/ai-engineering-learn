#!/usr/bin/env python3
"""Prove the LiteLLM proxy -> LangFuse pipeline end to end.

Makes ONE throwaway completion through the proxy, then queries the LangFuse API
for that exact trace and prints its token counts and cost. Stdlib only.

Usage:
    uv run python services/proxy/verify_trace.py
    # or:  python3 services/proxy/verify_trace.py --model fallback

Reads config from .env.proxy at the repo root (ANTHROPIC/OPENAI keys not needed
here — only the proxy master key + LangFuse creds).
"""

# This is a stdlib probe that consumes untyped JSON (json.load -> Any), so the
# strict basedpyright extras (reportAny / reportUnknown*) would flag every field
# access. Drop just this script to standard type-checking; real errors still fire.
# pyright: standard

from __future__ import annotations

import argparse
import base64
import json
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env.proxy"
PROXY_URL = "http://localhost:4000"


def load_env(path: Path) -> dict[str, str]:
    """Minimal .env parser: KEY=VALUE lines, strips quotes and inline comments."""
    env: dict[str, str] = {}
    if not path.exists():
        sys.exit(f"error: {path} not found — copy .env.proxy.example and fill it in.")
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        # strip a trailing ` # comment` only when the value isn't quoted
        if value[:1] not in {'"', "'"} and " #" in value:
            value = value.split(" #", 1)[0].strip()
        value = value.strip().strip('"').strip("'")
        env[key.strip()] = value
    return env


def http_json(url: str, *, headers: dict[str, str], data: bytes | None = None):
    req = urllib.request.Request(url, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise SystemExit(f"HTTP {exc.code} from {url}\n{body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"cannot reach {url}: {exc.reason}") from exc


def make_completion(env: dict[str, str], model: str, marker: str) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": f"Reply with the single word: ok ({marker})",
                }
            ],
            "max_tokens": 10,
            "metadata": {"trace_name": marker},
        }
    ).encode()
    headers = {
        "Authorization": f"Bearer {env['LITELLM_MASTER_KEY']}",
        "Content-Type": "application/json",
    }
    return http_json(f"{PROXY_URL}/v1/chat/completions", headers=headers, data=body)


def find_trace(env: dict[str, str], marker: str, *, attempts: int = 12, delay: int = 5):
    host = env["LANGFUSE_HOST"].rstrip("/")
    auth = base64.b64encode(
        f"{env['LANGFUSE_PUBLIC_KEY']}:{env['LANGFUSE_SECRET_KEY']}".encode()
    ).decode()
    headers = {"Authorization": f"Basic {auth}"}
    for attempt in range(1, attempts + 1):
        data = http_json(
            f"{host}/api/public/observations?type=GENERATION&limit=50",
            headers=headers,
        )["data"]
        for obs in data:
            blob = json.dumps(obs.get("input")) + str(obs.get("name") or "")
            if marker in blob:
                return obs, host
        print(f"  attempt {attempt}/{attempts}: not visible yet, waiting {delay}s...")
        time.sleep(delay)
    return None, host


def show_trace_scores(
    env: dict[str, str], trace_id: str, *, attempts: int = 12, delay: int = 5
):
    """Fetch a trace by id and print its generation usage/cost + attached scores.

    Used to confirm the /chat service logged ttft_ms / total_latency_ms to the same
    trace the proxy created (pass the X-Trace-Id header the endpoint returns).
    """
    host = env["LANGFUSE_HOST"].rstrip("/")
    auth = base64.b64encode(
        f"{env['LANGFUSE_PUBLIC_KEY']}:{env['LANGFUSE_SECRET_KEY']}".encode()
    ).decode()
    headers = {"Authorization": f"Basic {auth}"}
    for attempt in range(1, attempts + 1):
        try:
            trace = http_json(f"{host}/api/public/traces/{trace_id}", headers=headers)
        except SystemExit:
            print(
                f"  attempt {attempt}/{attempts}: not ingested yet, waiting {delay}s..."
            )
            time.sleep(delay)
            continue
        scores = trace.get("scores") or []
        gens = [
            o for o in trace.get("observations") or [] if o.get("type") == "GENERATION"
        ]
        names = {s.get("name") for s in scores}
        if gens and {"ttft_ms", "total_latency_ms"} <= names:
            g = gens[0]
            u = g.get("usage") or {}
            print("\n--- TRACE FOUND IN LANGFUSE ---")
            print(f"  traceId:          {trace_id}")
            print(f"  name:             {trace.get('name')}")
            print(f"  session:          {trace.get('sessionId')}")
            print(f"  model:            {g.get('model')}")
            print(f"  tokens (in/out):  {u.get('input')} / {u.get('output')}")
            print(f"  TOTAL cost  ($):  {g.get('calculatedTotalCost')}")
            for s in scores:
                name, val, dtype = s.get("name"), s.get("value"), s.get("dataType")
                print(f"  score: {name} = {val} ({dtype})")
            print(f"  dashboard:        {host}/project/_/traces/{trace_id}")
            return 0
        print(f"  attempt {attempt}/{attempts}: waiting for scores, {delay}s...")
        time.sleep(delay)
    print(
        "\nNOT COMPLETE after polling — generation and/or ttft/latency scores missing."
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default="primary",
        help="proxy model group to call (default: primary)",
    )
    parser.add_argument(
        "--trace-id",
        help="skip the completion; just fetch this trace's generation + scores "
        "(the X-Trace-Id header /chat returns)",
    )
    args = parser.parse_args()

    env = load_env(ENV_FILE)
    for required in (
        "LITELLM_MASTER_KEY",
        "LANGFUSE_HOST",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
    ):
        if not env.get(required):
            sys.exit(f"error: {required} missing/empty in {ENV_FILE}")

    if args.trace_id:
        print(f"fetching trace {args.trace_id} ...")
        return show_trace_scores(env, args.trace_id)

    marker = f"proof-{secrets.token_hex(5)}"
    print(f"marker: {marker}")

    print(f"\n1) throwaway completion through proxy (model={args.model})")
    result = make_completion(env, args.model, marker)
    usage = result["usage"]
    reply = result["choices"][0]["message"]["content"]
    print(f"   reply: {reply!r}")
    print(
        f"   served-by: {result.get('model')} | "
        f"{usage['prompt_tokens']} in / {usage['completion_tokens']} out / "
        f"{usage['total_tokens']} total"
    )

    print("\n2) polling LangFuse API for the trace (async flush)...")
    obs, host = find_trace(env, marker)
    if obs is None:
        print("\nNOT FOUND after polling. The call succeeded, but the trace hasn't")
        print("appeared. Check LANGFUSE_* creds/host, or the callback in config.yaml.")
        return 1

    u = obs.get("usage") or {}
    print("\n--- TRACE FOUND IN LANGFUSE ---")
    print(f"  model:            {obs.get('model')}")
    print(f"  traceId:          {obs.get('traceId')}")
    print(f"  input tokens:     {u.get('input') or u.get('promptTokens')}")
    print(f"  output tokens:    {u.get('output') or u.get('completionTokens')}")
    print(f"  total tokens:     {u.get('total') or u.get('totalTokens')}")
    print(f"  input cost  ($):  {obs.get('calculatedInputCost')}")
    print(f"  output cost ($):  {obs.get('calculatedOutputCost')}")
    print(f"  TOTAL cost  ($):  {obs.get('calculatedTotalCost')}")
    print(f"  dashboard:        {host}/project/_/traces/{obs.get('traceId')}")

    if obs.get("calculatedTotalCost") is None:
        print("\n  NOTE: cost is null — LangFuse has no pricing for this model id yet.")
        print("  Add a model definition in LangFuse (Settings -> Models) to get cost.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
