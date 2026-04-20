from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import tempfile
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path

import openai

from cusco.models import EntityReport

logger = logging.getLogger(__name__)

# AI-generated overviews use a persistent cache location that survives
# backend restarts and system reboots. Bulk data sources (contracts, entities,
# etc.) still use CUSCO_CACHE_DIR (default /tmp/cusco_cache) since that data
# is easily re-downloaded, but LLM output is expensive and worth persisting.
#
# ONLY CUSCO_AI_CACHE_DIR is honoured for the AI cache. We intentionally do
# NOT fall back to CUSCO_CACHE_DIR/overviews — that path is often /tmp and
# ephemeral, which defeats the purpose of persisting expensive LLM output.
def _resolve_overview_cache_dir() -> Path:
    explicit = os.environ.get("CUSCO_AI_CACHE_DIR")
    if explicit:
        return Path(explicit)
    return Path.home() / ".cusco" / "cache" / "overviews"


OVERVIEW_CACHE_DIR = _resolve_overview_cache_dir()
# 30 days — hash-based invalidation catches real data changes, so the TTL
# is just a safety net for prompt tweaks or model upgrades.
CACHE_MAX_AGE_SECONDS = 30 * 24 * 3600

# Truncation limits — the overview prompt only needs a representative sample
# of contracts (plus aggregate stats already summarised in the report), not
# every single record. Keeping this small controls prompt size and cost.
MAX_CONTRACTS_IN_CONTEXT = 100
MAX_IBERINFORM_CHARS = 4000


# Accept only 9-digit NIFs (matches the /api/search validation). Used to
# prevent path traversal via client-supplied NIFs on POST /api/overview,
# where the body isn't validated by the route's query-string pattern.
_NIF_RE = re.compile(r"^\d{9}$")


def _safe_nif(nif: str) -> str:
    """Return the NIF if it matches the canonical 9-digit form, else raise.

    Callers use this before passing a user-supplied NIF to filesystem paths.
    """
    if not isinstance(nif, str) or not _NIF_RE.match(nif):
        raise ValueError(f"Invalid NIF for cache key: {nif!r}")
    return nif

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
    """Prepare an EntityReport for LLM consumption.

    - Caps the contracts list at MAX_CONTRACTS_IN_CONTEXT, adding a _note
      with the true total so the model can still answer aggregate questions.
    - Truncates oversized iberinform_content to MAX_IBERINFORM_CHARS.
    - Drops transient fields (queried_at, source_statuses) — they're request
      metadata, not company data, and they're noise for both narrative and
      Q&A contexts.
    """
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

    # Strip transient fields — they're noise for LLM context
    data.pop("queried_at", None)
    data.pop("source_statuses", None)

    return data


def build_overview_prompt(report: EntityReport) -> str:
    data = truncate_report_for_llm(report)
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
    # _safe_nif guarantees the NIF can't contain separators / traversal chars
    return OVERVIEW_CACHE_DIR / f"{_safe_nif(nif)}.json"


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


def _cleanup_expired_cache() -> None:
    """Remove overview cache files older than the TTL. Best-effort — any
    error is logged and swallowed so cleanup never breaks a request."""
    if not OVERVIEW_CACHE_DIR.exists():
        return
    cutoff = time.time() - CACHE_MAX_AGE_SECONDS
    try:
        for path in OVERVIEW_CACHE_DIR.glob("*.json"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                continue
    except OSError as e:
        logger.warning(f"Failed to cleanup overview cache: {e}")


def save_cached_overview(nif: str, report_hash: str, narrative: str) -> None:
    """Persist narrative atomically: write to temp file, rename into place.
    Prevents corrupt JSON if the server is killed mid-write. Also lazily
    evicts expired cache entries."""
    try:
        OVERVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cleanup_expired_cache()
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

    # Guard against client-supplied NIFs that don't match the canonical form
    # (POST /api/overview accepts the whole report from the client, so the
    # NIF isn't enforced by the search route's ^\d{9}$ pattern).
    try:
        _safe_nif(report.nif)
    except ValueError as e:
        logger.warning(f"Overview rejected: {e}")
        yield _sse_event("error", message="Invalid NIF")
        yield _sse_event("done")
        return

    report_hash = _hash_report_for_cache(report)

    # Offload blocking disk I/O to a thread so we don't stall the event loop
    cached = await asyncio.to_thread(get_cached_overview, report.nif, report_hash)
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
        await asyncio.to_thread(
            save_cached_overview, report.nif, report_hash, narrative
        )

    yield _sse_event("done")
