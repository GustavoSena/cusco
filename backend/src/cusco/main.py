from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field
from .models import EntityReport, SourceResult, SourceStatus
from .sources import (
    NifSource,
    CitiusSource,
    DevedoresSource,
    ContractsSource,
    EntitiesSource,
    GleifSource,
    SegSocialSource,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Cusco starting — contract data will load on first query.")
    # Load contracts in background so the server starts immediately
    asyncio.create_task(_bg_load_contracts())
    asyncio.create_task(_bg_load_entities())
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


@app.get("/api/search")
async def search_entity(
    nif: str | None = Query(None, pattern=r"^\d{9}$", description="9-digit NIF"),
    name: str | None = Query(None, min_length=2, description="Company name"),
) -> EntityReport | NameSearchResult:
    """Search for a company/entity across all sources."""
    if not nif and not name:
        raise HTTPException(400, "Provide either 'nif' or 'name' parameter")

    if not nif:
        # Name search: try IMPIC entities and GLEIF to find matching NIFs
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
    ]

    results = await asyncio.gather(*tasks)

    # Aggregate into EntityReport
    report = EntityReport(nif=nif)

    for source_name, data, status in results:
        report.source_statuses.append(status)
        if data is None:
            continue

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
            # Enrich company name from entity profile if missing
            if report.company and not report.company.name:
                report.company.name = data["entity_profile"].name
        if "lei_record" in data and data["lei_record"] is not None:
            report.lei_record = data["lei_record"]
            # Enrich company name from LEI if still missing
            if report.company and not report.company.name:
                report.company.name = data["lei_record"].legal_name
        if "seg_social_procedures" in data:
            report.seg_social_procedures = data["seg_social_procedures"]
        if "seg_social_organisms" in data:
            report.seg_social_organisms = data["seg_social_organisms"]

    return report


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

        # IMPIC entities results
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

        # GLEIF results
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


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
