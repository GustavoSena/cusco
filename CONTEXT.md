# Cusco

**Cusco** is an AI-powered agent for exploring Portuguese public procurement data. It lets you search for companies and public contracts, uncover relationships between entities and municipalities, and visualize them as an interactive bubble graph.

Built for [Agents Day Braga 2026](https://taikai.network/en/layerx/hackathons/agents-day-braga-2026/overview).

## Problem

Public procurement data in Portugal (BASE/IMPIC) is open but hard to navigate. Understanding which companies win contracts in which municipalities, how much they're worth, and how concentrated the supplier landscape is requires manually cross-referencing multiple data sources. There's no easy way to ask natural language questions or see the big picture at a glance.

## Solution

Cusco is a conversational agent that:

- **Searches** companies by NIF or name and retrieves their public contract history
- **Searches** public contracts by municipality, year, price range, procedure type, or free text
- **Maps relationships** between contracting entities (municipalities/public bodies) and suppliers
- **Visualizes** these relationships as an interactive bubble graph where nodes are entities and edges are contracts, sized by value

## Data Source — ptdata.org API

All data comes from [api.ptdata.org](https://api.ptdata.org/), a unified Portuguese open data API. The API also exposes an MCP server at `https://api.ptdata.org/mcp` with 21 integrated tools.

### Key Endpoints

#### Contracts (`/v1/contracts`)

List and filter public procurement contracts from BASE/IMPIC.

| Parameter      | Type    | Description                        |
| -------------- | ------- | ---------------------------------- |
| `year`         | integer | Filter by contract year            |
| `entity`       | string  | Contracting entity NIF             |
| `supplier`     | string  | Supplier NIF                       |
| `district`     | string  | District code                      |
| `municipality` | string  | Municipality code                  |
| `procedure`    | string  | Procedure type                     |
| `cpv`          | string  | Common Procurement Vocabulary code |
| `min_price`    | number  | Minimum contract price (EUR)       |
| `max_price`    | number  | Maximum contract price (EUR)       |
| `q`            | string  | Full-text search on contract object|
| `limit`        | integer | Results per page (default: 50)     |
| `offset`       | integer | Pagination offset (default: 0)     |

**Response fields per contract:** `id`, `announcement_num`, `contract_type`, `procedure_type`, `object`, `description`, `contracting_entity`, `contracting_nif`, `suppliers[]`, `supplier_nifs[]`, `publication_date`, `signing_date`, `contract_price`, `base_price`, `actual_price`, `cpv_codes[]`, `execution_days`, `execution_location[]`, `district_code`, `municipality_code`, `year`, `close_date`.

#### Single Contract (`/v1/contracts/{id}`)

Get full details for a specific contract by its IMPIC ID.

#### Contract Statistics (`/v1/contracts/stats`)

Aggregated stats: `total_contracts`, `total_value_eur`, `avg_value_eur`, `contracts_this_year`, `value_this_year_eur`, `top_procedure_type`.

#### Company Lookup (`/v1/companies/{nif}`)

Aggregated company profile by NIF (9-digit tax number).

**Response fields:** `nif`, `valid`, `type`, `type_code`, `name`, `address`, `vat_active`, `cae_codes[]` (with `code`, `description`, `type`), `public_contracts` (with `total`, `total_value`, `recent[]`), `sources[]`.

#### NIF Validation (`/v1/fiscal/nif/{nif}`)

Validate a NIF and get its type: `nif`, `valid`, `type`, `type_code`, `check_digit`.

#### Geography (`/v1/geo/`)

- `GET /v1/geo/districts` — list all districts
- `GET /v1/geo/districts/{code}` — district detail (include municipalities)
- `GET /v1/geo/municipalities` — list/search municipalities (filter by `district`, `nuts_iii`, `q`; sort by `name`, `population`, `area_km2`)
- `GET /v1/geo/municipalities/{code}` — municipality detail (include parishes)
- `GET /v1/geo/parishes` — list/search parishes
- `GET /v1/geo/search?q=` — search across all geo levels

### Response Metadata

All responses include:
```json
{
  "meta": {
    "version": "...",
    "source": "...",
    "timestamp": "...",
    "docs": "..."
  }
}
```

### MCP Server

The API exposes an MCP (Model Context Protocol) server at `https://api.ptdata.org/mcp` with 21 tools, enabling direct integration with AI agents.

## Visualization Concept

The core visualization is a **bubble/network graph** showing:

- **Nodes:** Companies (suppliers) and contracting entities (municipalities, public bodies)
- **Edges:** Contracts linking a supplier to a contracting entity
- **Node size:** Total contract value for that entity
- **Edge thickness:** Value of contracts between two specific nodes
- **Color coding:** By district/region, entity type, or procedure type
- **Interactions:** Click a node to see details, filter by year/region/value, zoom into clusters

This makes it easy to spot:
- Which suppliers dominate a municipality's procurement
- Whether a company works across many municipalities or concentrates in one
- Unusually large contracts or suspiciously narrow supplier pools

## Architecture (Planned)

```
User (chat interface)
  │
  ▼
AI Agent (Claude + MCP tools)
  │
  ├── ptdata.org MCP server (contracts, companies, geo)
  │
  └── Graph builder (processes relationships)
        │
        ▼
  Interactive bubble graph (frontend)
```
