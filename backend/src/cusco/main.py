from __future__ import annotations

import asyncio
import logging
import os
import re as _re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

from pydantic import BaseModel, Field
from .chat import stream_chat
from .models import ChatRequest, EntityReport, SourceResult, SourceStatus
from .sources import (
    NifSource,
    CitiusSource,
    DevedoresSource,
    ContractsSource,
    EntitiesSource,
    IberinformSource,
    GleifSource,
    SegSocialSource,
    AdCSource,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Source singletons (initialized at startup) ---
nif_source = NifSource(timeout=10)
citius_source = CitiusSource(timeout=20)
devedores_source = DevedoresSource(timeout=60)
contracts_source = ContractsSource(timeout=120, years=[2026, 2025, 2024])
entities_source = EntitiesSource(timeout=120)
gleif_source = GleifSource(timeout=15)
seg_social_source = SegSocialSource(timeout=20)
iberinform_source = IberinformSource(timeout=60)
adc_source = AdCSource(timeout=60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Cusco starting — contract data will load on first query.")
    asyncio.create_task(_bg_load_contracts())
    asyncio.create_task(_bg_load_entities())
    asyncio.create_task(_bg_load_adc())
    yield
    logger.info("Cusco shutting down.")


async def _bg_load_contracts():
    try:
        await contracts_source._ensure_loaded()
        logger.info("Contract data loaded in background.")
    except Exception as e:
        logger.warning(f"Background contract load failed (will retry on query): {e}")


async def _bg_load_entities():
    try:
        await entities_source._ensure_loaded()
        logger.info("IMPIC entity data loaded in background.")
    except Exception as e:
        logger.warning(f"Background entity load failed (will retry on query): {e}")


async def _bg_load_adc():
    try:
        await adc_source._ensure_loaded()
        logger.info("AdC processes loaded in background.")
    except Exception as e:
        logger.warning(f"Background AdC load failed (will retry on query): {e}")


app = FastAPI(
    title="Cusco",
    description="Entity intelligence for Portuguese companies",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class NameSearchResult(BaseModel):
    """Result of a name search — list of matching entities."""

    query: str
    results: list[dict] = Field(default_factory=list)
    total_matches: int = 0


async def _run_source(name: str, coro) -> tuple[str, dict | None, SourceResult]:
    """Run a source query with timeout handling."""
    try:
        result = await coro
        return name, result, SourceResult(source=name, status=SourceStatus.OK)
    except asyncio.TimeoutError:
        logger.warning(f"Source {name} timed out")
        return name, None, SourceResult(source=name, status=SourceStatus.TIMEOUT, error="timeout")
    except Exception as e:
        logger.warning(f"Source {name} error: {e}")
        return name, None, SourceResult(source=name, status=SourceStatus.ERROR, error=str(e))


# Source names in the order they appear in the tasks list
_SOURCE_NAMES = [
    "nif", "citius", "devedores", "contracts",
    "entities", "gleif", "seg_social", "iberinform",
]


def _apply_source_data(report: EntityReport, source_name: str, data: dict | None):
    """Apply data from a single source to the report (mutates report)."""
    if data is None:
        return
    if "company" in data:
        report.company = data["company"]
    if "contracts" in data:
        report.contracts = data["contracts"]
        report.contracts_total_value = data.get("contracts_total_value", 0)
    if "insolvency_proceedings" in data:
        report.insolvency_proceedings = data["insolvency_proceedings"]
        report.has_insolvency = data.get("has_insolvency", False)
    if "debtor" in data:
        report.debtor = data["debtor"]
        report.is_tax_debtor = data.get("is_tax_debtor", False)
    if "entity_profile" in data and data["entity_profile"] is not None:
        report.entity_profile = data["entity_profile"]
        if report.company and not report.company.name:
            report.company.name = data["entity_profile"].name
    if "lei_record" in data and data["lei_record"] is not None:
        report.lei_record = data["lei_record"]
        if report.company and not report.company.name:
            report.company.name = data["lei_record"].legal_name
    if "seg_social_procedures" in data:
        report.seg_social_procedures = data["seg_social_procedures"]
    if "seg_social_organisms" in data:
        report.seg_social_organisms = data["seg_social_organisms"]
    if "iberinform_content" in data:
        report.iberinform_content = data["iberinform_content"]
    if "adc_processes" in data:
        report.adc_processes = data["adc_processes"]
        report.has_competition_issues = data.get("has_competition_issues", False)


async def _enrich_adc(report: EntityReport) -> None:
    """Cross-reference AdC by company name if no direct results."""
    if report.adc_processes:
        return

    company_name = None
    if report.company and report.company.name:
        company_name = report.company.name
    elif report.entity_profile and report.entity_profile.name:
        company_name = report.entity_profile.name
    elif report.lei_record and report.lei_record.legal_name:
        company_name = report.lei_record.legal_name

    if not company_name:
        return

    try:
        search_names = [company_name]
        core = _re.split(r"[,\-\u2013\u2014]", company_name)[0].strip()
        core = _re.sub(
            r"\s*(?:S\.?A\.?|LDA\.?|SGPS|Unipessoal|Comercial|"
            r"Portugal|Portuguesa)\s*$",
            "",
            core,
            flags=_re.IGNORECASE,
        ).strip()
        if core and core.lower() != company_name.lower() and len(core) >= 3:
            search_names.append(core)

        for search_name in search_names:
            adc_results = await adc_source.search_by_name(search_name)
            if adc_results.get("adc_processes"):
                report.adc_processes = adc_results["adc_processes"]
                report.has_competition_issues = adc_results.get(
                    "has_competition_issues", False
                )
                break
    except Exception as e:
        logger.warning(f"AdC name cross-reference failed: {e}")


@app.get("/api/search")
async def search_entity(
    nif: str | None = Query(None, pattern=r"^\d{9}$", description="9-digit NIF"),
    name: str | None = Query(None, min_length=2, description="Company name"),
) -> EntityReport | NameSearchResult:
    """Search for a company/entity across all sources."""
    if not nif and not name:
        raise HTTPException(400, "Provide either 'nif' or 'name' parameter")

    if not nif:
        return await _search_by_name(name)

    # Run all sources in parallel
    tasks = [
        _run_source("nif", nif_source.search_by_nif(nif)),
        _run_source("citius", citius_source.search_by_nif(nif)),
        _run_source("devedores", devedores_source.search_by_nif(nif)),
        _run_source("contracts", contracts_source.search_by_nif(nif)),
        _run_source("entities", entities_source.search_by_nif(nif)),
        _run_source("gleif", gleif_source.search_by_nif(nif)),
        _run_source("seg_social", seg_social_source.search_by_nif(nif)),
        _run_source("iberinform", iberinform_source.search_by_nif(nif)),
    ]

    results = await asyncio.gather(*tasks)

    report = EntityReport(nif=nif)

    for source_name, data, status in results:
        report.source_statuses.append(status)
        _apply_source_data(report, source_name, data)

    # AdC cross-reference by company name
    await _enrich_adc(report)

    return report


@app.get("/api/search/stream")
async def search_entity_stream(
    nif: str = Query(..., pattern=r"^\d{9}$", description="9-digit NIF"),
):
    """Stream search results as SSE — each source sends an event when it completes."""

    async def event_stream():
        report = EntityReport(nif=nif)
        report.source_statuses = [
            SourceResult(source=name, status=SourceStatus.PENDING)
            for name in _SOURCE_NAMES
        ]

        yield f"data: {report.model_dump_json()}\n\n"

        source_coros = {
            "nif": nif_source.search_by_nif(nif),
            "citius": citius_source.search_by_nif(nif),
            "devedores": devedores_source.search_by_nif(nif),
            "contracts": contracts_source.search_by_nif(nif),
            "entities": entities_source.search_by_nif(nif),
            "gleif": gleif_source.search_by_nif(nif),
            "seg_social": seg_social_source.search_by_nif(nif),
            "iberinform": iberinform_source.search_by_nif(nif),
        }

        async def run_and_tag(name: str, coro):
            _, data, status = await _run_source(name, coro)
            return name, data, status

        pending = {
            asyncio.create_task(run_and_tag(name, coro)): name
            for name, coro in source_coros.items()
        }

        while pending:
            done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                source_name = pending.pop(task)
                name, data, status = task.result()

                for i, s in enumerate(report.source_statuses):
                    if s.source == source_name:
                        report.source_statuses[i] = status
                        break

                _apply_source_data(report, source_name, data)
                yield f"data: {report.model_dump_json()}\n\n"

        # AdC cross-reference after all sources complete
        await _enrich_adc(report)
        yield f"data: {report.model_dump_json()}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _search_by_name(name: str) -> NameSearchResult:
    """Search for entities by name across IMPIC entities and GLEIF."""
    tasks = [
        _run_source("entities", entities_source.search_by_name(name)),
        _run_source("gleif", gleif_source.search_by_name(name)),
    ]
    results = await asyncio.gather(*tasks)

    matches = []
    seen_nifs: set[str] = set()

    for source_name, data, status in results:
        if data is None:
            continue

        if "entity_profiles" in data:
            for profile in data["entity_profiles"]:
                if profile.nif and profile.nif not in seen_nifs:
                    seen_nifs.add(profile.nif)
                    matches.append(
                        {
                            "nif": profile.nif,
                            "name": profile.name,
                            "source": "impic_entities",
                        }
                    )

        if "lei_records" in data:
            for record in data["lei_records"]:
                nif = record.registered_as
                if nif and nif not in seen_nifs:
                    seen_nifs.add(nif)
                    matches.append(
                        {
                            "nif": nif,
                            "name": record.legal_name,
                            "source": "gleif",
                            "lei": record.lei,
                        }
                    )

    return NameSearchResult(
        query=name,
        results=matches[:50],
        total_matches=len(matches),
    )


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Chat about an entity report using an LLM."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(500, "OpenAI API key not configured")
    return StreamingResponse(
        stream_chat(request.report, request.message, request.history),
        media_type="text/event-stream",
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
