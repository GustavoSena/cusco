# Cusco

Entity intelligence for Portuguese companies. Search by NIF or company name and get a consolidated report from 9+ government and public data sources.

## What it does

Enter a 9-digit NIF (tax ID) or company name and Cusco runs all checks in parallel, returning:

- **Company identity** — name, address, LEI status, entity type
- **Risk assessment** — insolvency proceedings, tax debtor status, competition authority sanctions
- **Public contracts** — full procurement history with prices, suppliers, and procedure types
- **Quick verdict** — synthesized risk/clear indicators at a glance

All data comes from official Portuguese government sources and public registries.

## Data sources

| Source | What it provides |
|--------|-----------------|
| [ptdata.org](https://api.ptdata.org) | NIF validation, entity type |
| [CITIUS](https://www.citius.mj.pt) | Insolvency proceedings (PER, PEAP, CIRE) |
| [Portal das Finanças](https://static.portaldasfinancas.gov.pt) | Tax debtor lists with debt brackets |
| [dados.gov.pt IMPIC](https://dados.gov.pt) | ~480K public contracts + 110K entity profiles |
| [GLEIF](https://api.gleif.org) | LEI records — legal name, address, entity status |
| [Autoridade da Concorrência](https://extranet.concorrencia.pt) | Competition authority cases and sanctions |
| [Segurança Social](https://www.seg-social.pt) | Public recruitment procedures |
| [Iberinform](https://www.iberinform.pt) | Company profile data (via Jina) |

## Quick start

```bash
# Both services at once
./dev.sh

# Or separately:

# Backend (Python 3.11+)
cd backend
pip install -e ".[dev]"
python -m playwright install chromium   # for AdC source
uvicorn cusco.main:app --reload --port 8000

# Frontend (Node 18+)
cd frontend
npm install
npm run dev
```

The backend downloads and indexes bulk data on first start (~1-2 min). Cached in `/tmp/cusco_cache/`.

Frontend runs on http://localhost:5173 and proxies `/api/*` to the backend on :8000.

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `JINA_API_KEY` | For company profiles | [Jina](https://jina.ai) API key for Iberinform scraping |
| `OPENAI_API_KEY` | For chat | OpenAI API key for the report chat feature |
| `CUSCO_CACHE_DIR` | No | Cache directory (default: `/tmp/cusco_cache`) |
| `CUSCO_CHAT_MODEL` | No | LLM model for chat (default: `gpt-5.1`) |

## API

```
GET  /api/search?nif={9-digit-NIF}    → EntityReport      (all sources in parallel)
GET  /api/search?name={company-name}  → NameSearchResult   (entity + GLEIF matches)
GET  /api/search/stream?nif={NIF}     → SSE stream         (progressive report updates)
POST /api/chat                        → SSE stream         (LLM chat about a report)
GET  /api/health                      → { status: "ok" }
```

## Project structure

```
cusco/
├── backend/
│   ├── pyproject.toml
│   └── src/cusco/
│       ├── main.py              # FastAPI app, endpoints, source orchestration
│       ├── models.py            # Pydantic models (EntityReport, Contract, etc.)
│       ├── chat.py              # LLM chat integration
│       └── sources/
│           ├── base.py          # Abstract DataSource base class
│           ├── nif.py           # ptdata.org NIF validation
│           ├── contracts.py     # IMPIC contracts (dados.gov.pt bulk)
│           ├── citius.py        # CITIUS insolvency scraper
│           ├── devedores.py     # Tax debtor PDFs
│           ├── entities.py      # IMPIC entity registry
│           ├── gleif.py         # GLEIF LEI records
│           ├── seg_social.py    # Seguranca Social procedures
│           ├── iberinform.py    # Iberinform company profiles
│           └── adc.py           # Autoridade da Concorrencia cases
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx              # Search flow + SSE streaming
│       ├── api/client.ts        # Typed API client
│       ├── types.ts             # TypeScript types (mirrors models.py)
│       └── components/          # Report sections, search, chat
├── dev.sh                       # Start both services
├── CONTEXT.md                   # Detailed project context
└── CLAUDE.md                    # AI coding assistant instructions
```

## Contributing

All changes go through pull requests — don't push directly to main.

1. Create a feature branch: `git checkout -b feat/your-feature`
2. Make your changes
3. Verify: `cd frontend && npm run build` and `cd backend && ruff check src`
4. Push and open a PR

See [CLAUDE.md](CLAUDE.md) for detailed architecture and conventions.

## License

Internal project.
