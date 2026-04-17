# Cusco

**Cusco** is an internal entity intelligence platform for Portuguese companies. Given a NIF (tax identification number), it aggregates data from multiple official government sources — public contracts, insolvency proceedings, tax debtor lists, competition authority sanctions, and more — into a single consolidated report.

## Problem

Assessing the financial health and public procurement history of a Portuguese company requires manually cross-referencing multiple government portals: Portal BASE for contracts, CITIUS for insolvency proceedings, Portal das Financas for tax debts. Each has a different interface, none talk to each other, and there's no single place to get a consolidated view.

## Solution

Cusco is a web app that takes a company NIF and runs all these checks in parallel, returning a unified entity report with:

- **NIF validation** — entity type (company/individual), validity
- **Public contracts** — full procurement history as supplier or contracting entity (2024-2026, ~170K contracts)
- **Insolvency proceedings** — active CIRE/PER/PEAP proceedings from CITIUS
- **Tax debtor status** — whether the entity appears on the AT public debtor list, with debt bracket

## Architecture

```
Frontend (React + Vite + Tailwind)
  │
  ▼
FastAPI Backend (:8000)
  │
  ├── /api/search?nif=...     → EntityReport (7 sources in parallel)
  ├── /api/search?name=...    → NameSearchResult (IMPIC entities + GLEIF)
  ├── /api/health             → status
  │
  ├── sources/nif.py          → ptdata.org NIF validation
  ├── sources/contracts.py    → dados.gov.pt IMPIC bulk contract data
  ├── sources/citius.py       → CITIUS insolvency scraper
  ├── sources/devedores.py    → AT debtor list PDFs
  ├── sources/entities.py     → IMPIC entity registry (110K+ entities)
  ├── sources/gleif.py        → GLEIF LEI records (company identity)
  └── sources/seg_social.py   → Segurança Social public procedures
```

Each data source is a separate module implementing a `DataSource` base class, making it straightforward to add new sources.

## Data Sources

### Active

| Source | Data | Method |
|--------|------|--------|
| **ptdata.org** `/v1/fiscal/nif/{nif}` | NIF validation, entity type | REST API (JSON) |
| **dados.gov.pt** IMPIC contracts dataset | Public contracts 2024-2026 with NIFs, prices, entities, procedure types | Bulk JSON download (ZIP), indexed in-memory by NIF |
| **CITIUS** `citius.mj.pt` | Insolvency proceedings (PER, PEAP, CIRE) by NIF | HTML scraping (ASP.NET form POST) |
| **Portal das Financas** debtor PDFs | Tax debtor lists for companies, 6 brackets from EUR 10K to >1M | PDF download + text extraction |
| **dados.gov.pt** IMPIC entities | 110K+ entities registered in Portal BASE — names, countries, contract stats | Bulk JSON download (~47MB), indexed in-memory by NIF and name |
| **GLEIF** `api.gleif.org` | LEI records — legal name, registered address, headquarters, entity status, jurisdiction, legal form | REST API (JSON, free, no auth) |
| **Segurança Social** `seg-social.pt` | Public recruitment/mobility procedures with organism metadata | REST JSON API |

### Planned (future iterations)

| Source | Data | Access | Notes |
|--------|------|--------|-------|
| **nif.pt API** | Company name, address, CAE codes, status | REST JSON (API key) | Requires paid API key |
| **publicacoes.mj.pt** | Commercial registry publications (formations, dissolutions, board changes) | HTML scraping | Blocked by reCAPTCHA — needs solver |
| **Portal BASE API** `base.gov.pt/base2/rest/contratos/` | Direct contract search | REST JSON (IMPIC auth required) | Requires auth |
| **eInforma API** | Comprehensive company data | REST JSON (paid) | Paid service |
| **PRR Entidades** (dados.gov.pt) | Entities receiving EU Recovery & Resilience Plan funding | XLSX bulk download | ~41MB, updated weekly |
| **PT2030 Entidades** (dados.gov.pt) | Entities in Portugal 2030 EU structural funds | XLSX bulk download | ~2MB, updated monthly |

### Investigated but not viable

| Source | Reason |
|--------|--------|
| **dre.tretas.org** | Returns 403 to all automated requests; SQLite dump is 1.4GB — impractical for app startup |
| **diariodarepublica.pt** | Pure JS SPA (OutSystems) with no REST API |
| **publicacoes.mj.pt** | Google reCAPTCHA v2 blocks all programmatic access |

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, httpx, BeautifulSoup4, PyMuPDF, Pydantic
- **Frontend:** React 19, Vite, TypeScript, TailwindCSS v4
- **Data:** In-memory NIF-indexed stores for contracts (~480K entries) and entities (~110K), cached PDFs

## Development

### Prerequisites

- Python 3.11+
- Node.js 18+

### Backend

```bash
cd backend
pip install -e ".[dev]"
uvicorn cusco.main:app --reload --port 8000
```

On first start, the backend downloads and indexes ~480K contract entries and ~110K entities from dados.gov.pt (takes 1-2 minutes). Data is cached in `/tmp/cusco_cache/`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api/*` to the FastAPI backend on port 8000.

### API

```
GET /api/search?nif={9-digit-NIF}    → EntityReport  (7 sources in parallel)
GET /api/search?name={company-name}  → NameSearchResult  (IMPIC entities + GLEIF)
GET /api/health                      → { status: "ok" }
```

## Project Structure

```
cusco/
├── backend/
│   ├── pyproject.toml
│   └── src/cusco/
│       ├── main.py             # FastAPI app, endpoints, source orchestration
│       ├── models.py           # Pydantic models (EntityReport, Contract, etc.)
│       └── sources/
│           ├── base.py         # Abstract DataSource base class
│           ├── nif.py          # ptdata.org NIF validation
│           ├── contracts.py    # IMPIC contract data (dados.gov.pt bulk)
│           ├── citius.py       # CITIUS insolvency scraper
│           ├── devedores.py    # AT debtor list PDFs
│           ├── entities.py     # IMPIC entity registry (dados.gov.pt bulk)
│           ├── gleif.py        # GLEIF LEI records (company identity)
│           └── seg_social.py   # Segurança Social public procedures
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx             # Main app with search flow
│       ├── api/client.ts       # Typed API client
│       ├── types.ts            # TypeScript types matching backend models
│       └── components/
│           ├── SearchBar.tsx
│           ├── EntityReport.tsx
│           ├── ContractsList.tsx
│           ├── InsolvencyBadge.tsx
│           └── DebtorStatus.tsx
├── CONTEXT.md
└── relevant-datasets.csv       # Curated list of relevant dados.gov.pt datasets
```
