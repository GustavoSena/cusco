# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cusco is an entity intelligence platform for Portuguese companies. Given a 9-digit NIF (tax identification number), it returns a consolidated report aggregating data from multiple government sources: NIF validation (ptdata.org), public contracts (dados.gov.pt IMPIC datasets), insolvency proceedings (CITIUS), and tax debtor status (Portal das Finanças).

## Commands

### Backend
```bash
# Install (from repo root)
cd backend && pip install -e ".[dev]"

# Run dev server (port 8000)
uvicorn cusco.main:app --reload --port 8000

# Lint
ruff check backend/src

# Tests
pytest backend/
```

First backend startup downloads and indexes ~170K contracts from dados.gov.pt (takes 1-2 minutes). Cached in `/tmp/cusco_cache/`.

### Frontend
```bash
# Install (from repo root)
cd frontend && npm install

# Run dev server (proxies /api/* to localhost:8000)
npm run dev

# Build
npm run build

# Lint
npm run lint
```

## Architecture

**Monorepo** with two independent services:

- `backend/` — Python 3.11+ FastAPI async service (`backend/src/cusco/`)
- `frontend/` — React 19 + TypeScript + Vite + TailwindCSS v4 SPA (`frontend/src/`)

### Backend

Entry point: `backend/src/cusco/main.py` — FastAPI app with two endpoints:
- `GET /api/search?nif={nif}` — returns `EntityReport` aggregating all sources
- `GET /api/health` — health check

**Data sources** (`backend/src/cusco/sources/`) are plugins extending `DataSource` ABC. Each implements `search_by_nif()` with its own timeout. All four sources run in parallel via `asyncio.gather()` with graceful degradation — one failing source doesn't block the report.

| Source | External system | Method |
|---|---|---|
| `NifSource` | ptdata.org REST API | JSON API call |
| `CitiusSource` | citius.mj.pt | ASP.NET form POST + HTML scraping |
| `ContractsSource` | dados.gov.pt ZIP datasets | Download, extract, index in-memory |
| `DevedoresSource` | Portal das Finanças PDFs | Download PDF, text extraction |

**Models** in `backend/src/cusco/models.py` — Pydantic models for all data types. Frontend TypeScript interfaces in `frontend/src/types.ts` mirror these.

**Caching**: File-based in `/tmp/cusco_cache/` (configurable via `CUSCO_CACHE_DIR`). Contracts: 24h TTL. Debtor PDFs: 7-day TTL.

### Frontend

`App.tsx` orchestrates search flow. API client in `api/client.ts` wraps fetch calls. Components:
- `SearchBar` — NIF input with 9-digit validation
- `EntityReport` — main report container with source status indicators
- `ContractsList` — sortable, paginated contracts table
- `InsolvencyBadge` / `DebtorStatus` — status cards with color-coded alerts

Vite dev server proxies `/api/*` to `http://localhost:8000` (configured in `vite.config.ts`).

### Adding a New Data Source

1. Create a new module in `backend/src/cusco/sources/`
2. Extend `DataSource` ABC, implement `search_by_nif()`
3. Add corresponding Pydantic models to `models.py`
4. Register the source in `main.py` lifespan with a timeout
5. Add the source results to `EntityReport`
6. Mirror new types in `frontend/src/types.ts`
