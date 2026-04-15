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

**Data sources** (`backend/src/cusco/sources/`) are plugins extending `DataSource` ABC. Each implements `search_by_nif()` with its own timeout. All 7 sources run in parallel via `asyncio.gather()` with graceful degradation — one failing source doesn't block the report.

| Source | External system | Method | Key data returned |
|---|---|---|---|
| `NifSource` | ptdata.org REST API | JSON API call | NIF validity, entity type |
| `CitiusSource` | citius.mj.pt | ASP.NET form POST + HTML scraping | Insolvency proceedings (PER/PEAP/CIRE) |
| `ContractsSource` | dados.gov.pt ZIP datasets | Download, extract, index in-memory | Public contracts with prices, suppliers |
| `DevedoresSource` | Portal das Finanças PDFs | Download PDF, text extraction | Tax debtor status + debt bracket |
| `EntitiesSource` | dados.gov.pt entities JSON | Download, index in-memory by NIF+name | Company name, country, contract stats |
| `GleifSource` | api.gleif.org REST API | JSON API call (free, no auth) | LEI code, legal name, address, entity status |
| `SegSocialSource` | seg-social.pt REST API | JSON API call | Public recruitment procedures, organisms |

**Models** in `backend/src/cusco/models.py` — Pydantic models for all data types. Frontend TypeScript interfaces in `frontend/src/types.ts` must mirror these (see "Frontend integration" below).

**Caching**: File-based in `/tmp/cusco_cache/` (configurable via `CUSCO_CACHE_DIR`). Contracts: 24h TTL. Entities: 24h TTL. Debtor PDFs: 7-day TTL.

**Bulk data loading**: `ContractsSource` and `EntitiesSource` load large datasets into memory at startup via background tasks. The server starts immediately and serves requests while data loads. Until loaded, those sources return empty results (not errors).

### API endpoints

```
GET /api/search?nif={9-digit-NIF}    → EntityReport     (all 7 sources in parallel)
GET /api/search?name={company-name}  → NameSearchResult  (IMPIC entities + GLEIF)
GET /api/health                      → { status: "ok" }
```

**NIF search** returns an `EntityReport` with data from all sources. **Name search** returns a `NameSearchResult` with a list of `{nif, name, source}` matches from IMPIC entities (110K+ entities) and GLEIF. These are different response shapes — the frontend should check which type was returned.

**Company name enrichment**: The `NifSource` (ptdata.org) does NOT return company names. The backend automatically fills `company.name` from `EntitiesSource` or `GleifSource` if available, so the frontend doesn't need to handle this.

### Frontend

`App.tsx` orchestrates search flow. API client in `api/client.ts` wraps fetch calls. Components:
- `SearchBar` — NIF input with 9-digit validation
- `EntityReport` — main report container with source status indicators
- `ContractsList` — sortable, paginated contracts table
- `InsolvencyBadge` / `DebtorStatus` — status cards with color-coded alerts

Vite dev server proxies `/api/*` to `http://localhost:8000` (configured in `vite.config.ts`).

### Frontend integration — new fields added to EntityReport

The backend `EntityReport` now includes these additional fields that the frontend `types.ts` and components need to support:

```typescript
// --- ADD these new interfaces to frontend/src/types.ts ---

export interface EntityProfile {
  nif: string;
  name: string;
  country: string | null;
  country_code: string | null;
  total_contracts: number | null;
  times_as_supplier: number | null;
  total_value_as_supplier: number | null;
  times_as_entity: number | null;
  total_value_as_entity: number | null;
}

export interface LEIRecord {
  lei: string;
  legal_name: string;
  other_names: string[];
  legal_address: string;
  legal_city: string;
  legal_region: string;
  legal_country: string;
  legal_postal_code: string;
  headquarters_address: string;
  headquarters_city: string;
  headquarters_country: string;
  registered_as: string;
  jurisdiction: string;
  entity_status: string;
  entity_category: string;
  legal_form_code: string;
  registration_status: string;
  initial_registration_date: string;
  last_update_date: string;
  next_renewal_date: string;
}

export interface SegSocialProcedure {
  code: string;
  title: string;
  variant: string;
  scope: string;
  procedure_type: string;
  career: string;
  service: string;
  publication_date: string;
  expiration_date: string;
  organism_id: string;
  organism_name: string;
  organism_acronym: string;
  documents: { title: string; url: string }[];
}

export interface SegSocialOrganism {
  id: string;
  name: string;
  acronym: string;
  procedure_count: number;
}

export interface NameSearchResult {
  query: string;
  results: { nif: string; name: string; source: string; lei?: string }[];
  total_matches: number;
}

// --- ADD these fields to the existing EntityReport interface ---
// entity_profile: EntityProfile | null;
// lei_record: LEIRecord | null;
// seg_social_procedures: SegSocialProcedure[];
// seg_social_organisms: SegSocialOrganism[];
```

**What the frontend should display with the new data:**

1. **Entity Profile** (`entity_profile`): Show IMPIC contract aggregation stats — total contracts, total value as supplier/entity. Useful as a summary card. Available for ~110K entities.

2. **LEI Record** (`lei_record`): Show registered address, headquarters, entity status (ACTIVE/INACTIVE), LEI code. Rich identity data, but only available for ~10K Portuguese entities (mainly financial/listed companies). Display when present, hide when null.

3. **Seg Social** (`seg_social_procedures`, `seg_social_organisms`): Public sector recruitment procedures grouped by organism. Lower priority for display — useful as supplementary government activity data.

4. **Name Search**: The `/api/search?name=...` endpoint returns `NameSearchResult` (not `EntityReport`). The frontend needs a name search mode in `SearchBar` and a results list component where clicking a result triggers a NIF search. The API client needs a `searchByName(name)` function.

### Adding a New Data Source

1. Create a new module in `backend/src/cusco/sources/`
2. Extend `DataSource` ABC, implement `search_by_nif()` (optionally `search_by_name()`)
3. Add corresponding Pydantic models to `models.py`
4. Register the source in `main.py` — add singleton, add to parallel tasks list, add result aggregation
5. If the source needs bulk data loading, add a background task in the `lifespan` handler
6. Add the new fields to `EntityReport` in `models.py`
7. Export from `sources/__init__.py`
8. Mirror new types in `frontend/src/types.ts`
