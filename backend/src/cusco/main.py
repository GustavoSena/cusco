from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import EntityReport, SourceResult, SourceStatus
from .sources import NifSource, CitiusSource, DevedoresSource, ContractsSource

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Source singletons (initialized at startup) ---
nif_source = NifSource(timeout=10)
citius_source = CitiusSource(timeout=20)
devedores_source = DevedoresSource(timeout=60)
contracts_source = ContractsSource(timeout=120, years=[2026, 2025, 2024])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Cusco starting — contract data will load on first query.")
    # Load contracts in background so the server starts immediately
    asyncio.create_task(_bg_load_contracts())
    yield
    logger.info("Cusco shutting down.")


async def _bg_load_contracts():
    try:
        await contracts_source._ensure_loaded()
        logger.info("Contract data loaded in background.")
    except Exception as e:
        logger.warning(f"Background contract load failed (will retry on query): {e}")


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


@app.get("/api/search", response_model=EntityReport)
async def search_entity(
    nif: str | None = Query(None, pattern=r"^\d{9}$", description="9-digit NIF"),
    name: str | None = Query(None, min_length=2, description="Company name"),
):
    """Search for a company/entity across all sources."""
    if not nif and not name:
        raise HTTPException(400, "Provide either 'nif' or 'name' parameter")

    if not nif:
        # TODO: implement name-to-NIF lookup once we have a name search source
        raise HTTPException(
            501, "Name search not yet implemented — please provide a NIF"
        )

    # Run all sources in parallel
    tasks = [
        _run_source("nif", nif_source.search_by_nif(nif)),
        _run_source("citius", citius_source.search_by_nif(nif)),
        _run_source("devedores", devedores_source.search_by_nif(nif)),
        _run_source("contracts", contracts_source.search_by_nif(nif)),
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

    return report


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
