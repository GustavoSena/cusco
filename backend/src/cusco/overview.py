from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import tempfile
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path

import openai

from cusco.models import EntityReport

logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.environ.get("CUSCO_CACHE_DIR", "/tmp/cusco_cache"))
OVERVIEW_CACHE_DIR = CACHE_DIR / "overviews"
CACHE_MAX_AGE_SECONDS = 24 * 3600  # 24 hours — same as contracts

# Truncation limits shared with chat.py — keeps LLM context size predictable
MAX_CONTRACTS_IN_CONTEXT = 5100
MAX_IBERINFORM_CHARS = 4000

# Fake-streaming parameters for cache hits
_CACHED_CHUNK_SIZE = 20
_CACHED_CHUNK_DELAY_SECONDS = 0.015


OVERVIEW_SYSTEM_PROMPT = """\
You are an analyst writing a concise company intelligence brief for a Portuguese \
entity (NIF {nif}). Given the structured report data below, produce a 2-4 \
paragraph narrative that a business analyst would write for a colleague.

Cover the following topics when the data supports them:
- Company identity: legal name, entity type, jurisdiction, registration status, \
  and any LEI/address details worth noting.
- Public procurement activity: total contract count and value, whether the \
  entity acts mostly as a supplier or as a contracting entity, notable sectors \
  or counterparties if evident.
- Risk signals: insolvency proceedings (CITIUS), tax debtor status (Portal das \
  Finanças), competition authority (AdC) processes. If none are present, note \
  the absence briefly.
- Any notable details from Iberinform or LEI data (credit/solvency notes, \
  corporate structure, headquarters differences).

Write in a neutral analyst tone. Do not use bullet points — use paragraphs. \
Do not include headers. Do not hedge excessively. If data is missing for a \
topic, skip that topic. Do not end with disclaimers. Write in English.

Report data:
{report_json}
"""


def truncate_report_for_llm(report: EntityReport) -> dict:
    """Shared truncation helper. Keeps the LLM context predictable by capping
    contract list size and Iberinform content. Drops transient fields that
    don't affect either a narrative or Q&A (queried_at, source_statuses)."""
    data = report.model_dump(mode="json")

    if len(data.get("contracts", [])) > MAX_CONTRACTS_IN_CONTEXT:
        total = len(data["contracts"])
        data["contracts"] = data["contracts"][:MAX_CONTRACTS_IN_CONTEXT]
        data["_note"] = (
            f"Showing {MAX_CONTRACTS_IN_CONTEXT} of {total} contracts. "
            f"Total contract value across all {total}: {report.contracts_total_value}"
        )

    if data.get("iberinform_content"):
        content = data["iberinform_content"]
        if len(content) > MAX_IBERINFORM_CHARS:
            data["iberinform_content"] = (
                content[:MAX_IBERINFORM_CHARS] + "\n...(truncated)"
            )

    return data


def build_overview_prompt(report: EntityReport) -> str:
    data = truncate_report_for_llm(report)
    # Overview narrative doesn't need per-source status or timestamp
    data.pop("queried_at", None)
    data.pop("source_statuses", None)
    report_json = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    return OVERVIEW_SYSTEM_PROMPT.format(nif=report.nif, report_json=report_json)


def _hash_report_for_cache(report: EntityReport) -> str:
    """Stable short hash of the report fields that influence the narrative.

    Excludes timestamps and per-source status metadata so that transient
    pending/retry noise doesn't invalidate an otherwise unchanged report."""
    data = report.model_dump(mode="json")
    data.pop("queried_at", None)
    data.pop("source_statuses", None)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _cache_file(nif: str) -> Path:
    return OVERVIEW_CACHE_DIR / f"{nif}.json"


def get_cached_overview(nif: str, report_hash: str) -> str | None:
    path = _cache_file(nif)
    if not path.exists():
        return None

    age = time.time() - path.stat().st_mtime
    if age >= CACHE_MAX_AGE_SECONDS:
        return None

    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to read cached overview for {nif}: {e}")
        return None

    if payload.get("hash") != report_hash:
        return None

    narrative = payload.get("narrative")
    if not isinstance(narrative, str) or not narrative:
        return None
    return narrative


def save_cached_overview(nif: str, report_hash: str, narrative: str) -> None:
    """Persist narrative atomically: write to temp file, rename into place.
    Prevents corrupt JSON if the server is killed mid-write."""
    try:
        OVERVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "hash": report_hash,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "narrative": narrative,
        }
        target = _cache_file(nif)
        # Write to tmp file in same dir then os.replace for atomicity
        fd, tmp_path = tempfile.mkstemp(
            dir=OVERVIEW_CACHE_DIR, prefix=f".{nif}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            os.replace(tmp_path, target)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError as e:
        logger.warning(f"Failed to save cached overview for {nif}: {e}")


def _sse_event(event_type: str, **kwargs) -> str:
    """Emit a JSON-encoded SSE event. Protects against LLM output containing
    newlines or the literal string '[DONE]' which would break plain-text SSE."""
    payload = json.dumps({"type": event_type, **kwargs}, ensure_ascii=False)
    return f"data: {payload}\n\n"


async def _stream_cached(narrative: str) -> AsyncGenerator[str, None]:
    """Stream a cached narrative back as SSE chunks for UI consistency."""
    for i in range(0, len(narrative), _CACHED_CHUNK_SIZE):
        yield _sse_event("chunk", text=narrative[i : i + _CACHED_CHUNK_SIZE])
        await asyncio.sleep(_CACHED_CHUNK_DELAY_SECONDS)


async def stream_overview(report: EntityReport) -> AsyncGenerator[str, None]:
    """Stream an LLM-generated company overview as JSON-encoded SSE events.

    Event types:
      {"type": "chunk", "text": "..."}      — narrative chunk
      {"type": "error", "message": "..."}   — generation failed
      {"type": "done"}                      — stream complete
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        yield _sse_event("error", message="OpenAI API key not configured")
        yield _sse_event("done")
        return

    report_hash = _hash_report_for_cache(report)

    cached = get_cached_overview(report.nif, report_hash)
    if cached is not None:
        async for chunk in _stream_cached(cached):
            yield chunk
        yield _sse_event("done")
        return

    client = openai.AsyncOpenAI(api_key=api_key)
    model = os.getenv("CUSCO_CHAT_MODEL", "gpt-5.1")
    prompt = build_overview_prompt(report)

    collected: list[str] = []

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": prompt}],
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                collected.append(delta.content)
                yield _sse_event("chunk", text=delta.content)
    except openai.RateLimitError:
        yield _sse_event(
            "error",
            message="OpenAI rate limit exceeded. Please try again in a moment.",
        )
        yield _sse_event("done")
        return
    except openai.APIError as e:
        yield _sse_event("error", message=str(e.message))
        yield _sse_event("done")
        return

    narrative = "".join(collected).strip()
    if narrative:
        save_cached_overview(report.nif, report_hash, narrative)

    yield _sse_event("done")
