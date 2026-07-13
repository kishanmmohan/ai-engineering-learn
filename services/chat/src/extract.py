"""Structured extraction for the /extract endpoint.

Given raw text plus a caller-supplied JSON Schema, return a JSON value that
validates against that schema — or, when the model cannot produce one within a
capped retry budget, raise a typed ExtractionError the endpoint turns into a
clean error object (never malformed output, never a 500 stack trace).

Two extraction modes, chosen per request, so their failure modes can be compared
(this is the point of Break-It #2):

- "native": pass a `response_format` json_schema to the proxy. Through LiteLLM
  this is translated PER PROVIDER — for `primary` (Anthropic) it becomes a forced
  tool call (server-side JSON-mode enforcement); for the `fallback` (OpenAI) it is
  real strict json_schema. Note: services/proxy/config.yaml sets `drop_params:
  true`, so if a provider path does not support the param it is SILENTLY dropped —
  you can think you are in native mode and not be. We log the mode we sent.
- "prompt": no `response_format`; the schema is embedded in the prompt with a
  "return only JSON" instruction. Enforcement is nothing but the model's obedience.

Either way, enforcement guarantees SHAPE at best, never that the payload is correct
or matches your exact schema — so we validate the parsed result regardless of mode,
and re-prompt with the validation error fed back on failure. Greedy decoding
(temperature=0) does not guarantee globally valid structure either, which is exactly
why validate-then-retry exists rather than trusting the sampler.

Provider calls go through the LiteLLM proxy via the `litellm_proxy/` prefix +
`api_base`, reusing the same wiring as ai_client (see its module docstring).
"""

import json
import os
from typing import Literal, cast, final

import litellm
import structlog

# _langfuse is module-private in ai_client but deliberately shared here: /extract and
# /chat attach scores to the same LangFuse instance rather than each build their own.
from .ai_client import (
    MASTER_KEY,
    PROXY_URL,
    _langfuse,  # pyright: ignore[reportPrivateUsage]
)

Mode = Literal["native", "prompt"]
# The two ways extraction can fail after the model is called and returns.
FailureKind = Literal["parse", "schema"]

# Sampling temperature for the extraction endpoint. Pinned to 0 (greedy decoding:
# take the arg-max token at each step) rather than /chat's 0.7. Extraction is a
# closed task — the answer is fixed by the input — so we want the mode of the
# next-token distribution, not variety; greedy decoding minimises excursions into
# the low-probability regions where malformed tokens live and makes a given failure
# reproducible (so a retry or an eval means something). It is NOT byte-deterministic
# and does NOT guarantee valid structure, which is why we still validate + retry.
# (Tune temperature OR top_p, never both — see system_prompt.md.)
EXTRACT_TEMPERATURE = float(os.environ.get("EXTRACT_TEMPERATURE", "0"))

# Retries AFTER the first attempt (so total attempts = N + 1). At temperature 0 a
# bare retry re-rolls almost the same output; the lever that actually changes the
# next attempt is feeding the parse/validation error back into the messages. So a
# small N is enough — more mostly buys latency and spend for diminishing return.
EXTRACT_MAX_RETRIES = int(os.environ.get("EXTRACT_MAX_RETRIES", "2"))

# Which mode a request uses when it does not specify one. Any value other than
# "prompt" (including unset) resolves to "native".
EXTRACT_DEFAULT_MODE: Mode = (
    "prompt" if os.environ.get("EXTRACT_DEFAULT_MODE") == "prompt" else "native"
)

log: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]


@final
class ExtractionError(Exception):
    """Raised when extraction exhausts its retry budget without valid output.

    Carries structured fields so the endpoint can render a typed error body.
    """

    def __init__(
        self,
        *,
        attempts: int,
        mode: Mode,
        kind: FailureKind,
        detail: str,
        last_raw: str | None = None,
    ) -> None:
        self.attempts: int = attempts
        self.mode: Mode = mode
        self.kind: FailureKind = kind
        self.detail: str = detail
        self.last_raw: str | None = last_raw
        super().__init__(
            f"extraction failed after {attempts} attempt(s) in {mode} mode ({detail})"
        )


def _initial_messages(
    text: str, json_schema: dict[str, object], mode: Mode
) -> list[dict[str, str]]:
    """Build the first request. In native mode the schema is enforced via
    response_format, so the prompt stays lean; in prompt mode the schema is the
    only thing steering the model, so it is embedded verbatim."""
    if mode == "native":
        return [
            {
                "role": "system",
                "content": (
                    "You extract structured data from text. Return a single JSON "
                    "object matching the required schema. No prose, no markdown."
                ),
            },
            {"role": "user", "content": f"Extract data from this text:\n\n{text}"},
        ]
    return [
        {
            "role": "system",
            "content": (
                "You extract structured data from text. Return ONLY a single JSON "
                "value — no prose, no explanation, no markdown code fences."
            ),
        },
        {
            "role": "user",
            "content": (
                "Extract data conforming to this JSON Schema:\n\n"
                f"{json.dumps(json_schema)}\n\n"
                f"Text:\n\n{text}\n\n"
                "Return only the JSON."
            ),
        },
    ]


def _record(trace_id: str, *, attempts: int, outcome: str) -> None:
    """Attach the attempt count + outcome to the LangFuse trace. Never raises —
    observability must not turn a working extraction into an error."""
    try:
        _langfuse.create_score(
            trace_id=trace_id,
            name="extract_attempts",
            value=attempts,
            data_type="NUMERIC",
        )
        _langfuse.create_score(
            trace_id=trace_id,
            name="extract_outcome",
            value=outcome,
            data_type="CATEGORICAL",
        )
    except Exception as exc:
        log.warning("langfuse_score_failed", trace_id=trace_id, error=str(exc))


def extract(
    *,
    text: str,
    json_schema: dict[str, object],
    mode: Mode,
    trace_id: str,
    model: str = "primary",
) -> object:
    """Extract schema-valid JSON from `text`, retrying on invalid output.

    Returns the parsed, schema-validated value on success. Raises ExtractionError
    once the retry budget (EXTRACT_MAX_RETRIES) is spent. Each attempt is a separate
    proxy call carrying the same `trace_id`, so the retry loop shows up as multiple
    generations under one trace in LangFuse.
    """
    # Import jsonschema lazily so a missing schema-check dep can't break module load.
    import jsonschema

    total_attempts = EXTRACT_MAX_RETRIES + 1
    # None in prompt mode (no enforcement); a json_schema block in native mode. The
    # proxy translates the block per provider (Anthropic -> forced tool call, OpenAI
    # -> strict json_schema). See module docstring.
    response_format: dict[str, object] | None = None
    if mode == "native":
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "schema": json_schema,
                "name": "extraction",
                "strict": True,
            },
        }

    messages = _initial_messages(text, json_schema, mode)
    last_kind: FailureKind = "parse"
    last_detail = ""
    last_raw: str | None = None

    for attempt in range(1, total_attempts + 1):
        metadata = {
            "trace_id": trace_id,
            "trace_name": "extract",
            "extract_mode": mode,
            "extract_attempt": str(attempt),
        }
        # metadata rides in extra_body so the proxy's LangFuse callback sees it (the
        # SDK's own metadata= kwarg is consumed locally in proxy mode). cast() narrows
        # the non-streaming return to ModelResponse for the type checker.
        # litellm ships incomplete type stubs for completion().
        response = cast(
            litellm.ModelResponse,
            litellm.completion(  # pyright: ignore[reportUnknownMemberType]
                model=f"litellm_proxy/{model}",
                api_base=PROXY_URL,
                api_key=MASTER_KEY,
                messages=messages,
                temperature=EXTRACT_TEMPERATURE,
                extra_body={"metadata": metadata},
                response_format=response_format,
            ),
        )
        raw = response.choices[0].message.content or ""
        last_raw = raw

        try:
            instance = cast(object, json.loads(raw))
        except json.JSONDecodeError as exc:
            last_kind, last_detail = "parse", str(exc)
            log.warning(
                "extract_parse_failed",
                trace_id=trace_id,
                attempt=attempt,
                mode=mode,
                error=last_detail,
            )
            messages = [
                *messages,
                {"role": "assistant", "content": raw},
                {
                    "role": "user",
                    "content": (
                        f"That was not valid JSON ({exc}). Return ONLY a single "
                        "valid JSON value — no prose, no markdown code fences."
                    ),
                },
            ]
            continue

        try:
            jsonschema.validate(instance, json_schema)
        except jsonschema.ValidationError as exc:
            last_kind, last_detail = "schema", exc.message
            log.warning(
                "extract_schema_failed",
                trace_id=trace_id,
                attempt=attempt,
                mode=mode,
                error=last_detail,
            )
            messages = [
                *messages,
                {"role": "assistant", "content": raw},
                {
                    "role": "user",
                    "content": (
                        f"Your JSON failed schema validation: {exc.message}. "
                        "Fix it and return ONLY the corrected JSON value."
                    ),
                },
            ]
            continue

        log.info("extract_success", trace_id=trace_id, attempts=attempt, mode=mode)
        _record(trace_id, attempts=attempt, outcome="success")
        return instance

    log.warning(
        "extract_exhausted",
        trace_id=trace_id,
        attempts=total_attempts,
        mode=mode,
        kind=last_kind,
    )
    _record(trace_id, attempts=total_attempts, outcome=f"failed_{last_kind}")
    raise ExtractionError(
        attempts=total_attempts,
        mode=mode,
        kind=last_kind,
        detail=last_detail,
        last_raw=last_raw,
    )
