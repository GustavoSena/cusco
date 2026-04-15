# Cusco

**Cusco** is an entity intelligence platform for Portuguese companies. Given a NIF (tax identification number), it aggregates data from multiple official government sources — public contracts, insolvency proceedings, and tax debtor lists — into a single report.

Built for [Agents Day Braga 2026](https://taikai.network/en/layerx/hackathons/agents-day-braga-2026/overview).

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
  ├── /api/search?nif=...     → EntityReport (all sources in parallel)
  ├── /api/health             → status
  │
  ├── sources/nif.py          → ptdata.org NIF validation
  ├── sources/contracts.py    → dados.gov.pt IMPIC bulk data
  ├── sources/citius.py       → CITIUS insolvency scraper
  └── sources/devedores.py    → AT debtor list PDFs
```

Each data source is a separate module implementing a `DataSource` base class, making it straightforward to add new sources.

## Data Sources

### Active (this iteration)

| Source | Data | Method |
|--------|------|--------|
| **ptdata.org** `/v1/fiscal/nif/{nif}` | NIF validation, entity type | REST API (JSON) |
| **dados.gov.pt** IMPIC contracts dataset | Public contracts 2024-2026 with NIFs, prices, entities, procedure types | Bulk JSON download (ZIP), indexed in-memory by NIF |
| **CITIUS** `citius.mj.pt` | Insolvency proceedings (PER, PEAP, CIRE) by NIF | HTML scraping (ASP.NET form POST) |
| **Portal das Financas** debtor PDFs | Tax debtor lists for companies, 6 brackets from EUR 10K to >1M | PDF download + text extraction |

### Planned (future iterations)

| Source | Data | Access |
|--------|------|--------|
| **dados.gov.pt IMPIC entities** | All entities registered in Portal BASE (46.7MB JSON) | Bulk download |
| **dre.tretas.org** | Full Diario da Republica database — insolvency notices in Serie 2 | SQLite/JSON dump |
| **nif.pt API** | Company name, address, CAE codes, status | REST JSON (API key) |
| **publicacoes.mj.pt** | Commercial registry publications (formations, dissolutions, board changes) | HTML scraping |
| **Portal BASE API** `base.gov.pt/base2/rest/contratos/` | Direct contract search | REST JSON (IMPIC auth required) |
| **eInforma API** | Comprehensive company data | REST JSON (paid) |

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, httpx, BeautifulSoup4, PyMuPDF, Pydantic
- **Frontend:** React 19, Vite, TypeScript, TailwindCSS v4
- **Data:** In-memory NIF-indexed contract store from IMPIC bulk data, cached PDFs

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

On first start, the backend downloads and indexes ~170K contracts from dados.gov.pt (takes 1-2 minutes). Data is cached in `/tmp/cusco_cache/`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api/*` to the FastAPI backend on port 8000.

### API

```
GET /api/search?nif={9-digit-NIF}  → EntityReport
GET /api/health                     → { status: "ok" }
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
│           └── devedores.py    # AT debtor list PDFs
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
