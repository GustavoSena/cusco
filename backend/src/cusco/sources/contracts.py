from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import re
import zipfile
from typing import Any

from ..models import Contract
from ..storage import BulkTable
from .base import DataSource

logger = logging.getLogger(__name__)

DADOS_GOV_BASE = "https://dados.gov.pt/s/resources/contratos-publicos-portal-base-impic-contratos-de-2012-a-2026"

# We'll load the most recent years for faster startup
DEFAULT_YEARS = [2026, 2025, 2024]

# Freshness window for the SQLite tables. Matches the previous 24h JSON
# cache TTL — if the tables are fresher than this we skip the download
# entirely and just serve queries from disk.
CACHE_MAX_AGE_SECONDS = 24 * 3600  # 1 day


class ContractsSource(DataSource):
    name = "impic_contracts"

    def __init__(self, timeout: float = 120.0, years: list[int] | None = None):
        super().__init__(timeout=timeout)
        self.years = years or DEFAULT_YEARS
        # Two SQLite tables, one per role. Each row is (nif, contract_dict_json)
        # — same edge-list shape the old in-memory dicts held, which keeps
        # `_aggregate_municipalities` and the rest of the read path untouched.
        self._supplier_table = BulkTable("contracts_supplier")
        self._entity_table = BulkTable("contracts_entity")
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        """Ensure the SQLite tables are fresh before serving queries.

        Serialized via `_load_once` so concurrent first queries don't each
        re-download + re-parse the (large) dataset.
        """
        await self._load_once(self._do_load, lambda: self._loaded)

    async def _do_load(self) -> None:
        # If both tables are fresh, skip the download entirely.
        supplier_fresh = await asyncio.to_thread(
            self._supplier_table.is_fresh, CACHE_MAX_AGE_SECONDS
        )
        entity_fresh = await asyncio.to_thread(
            self._entity_table.is_fresh, CACHE_MAX_AGE_SECONDS
        )
        if supplier_fresh and entity_fresh:
            supplier_rows = await asyncio.to_thread(self._supplier_table.row_count)
            entity_rows = await asyncio.to_thread(self._entity_table.row_count)
            logger.info(
                f"Contracts: SQLite fresh — {supplier_rows} supplier rows, "
                f"{entity_rows} entity rows (skipping download)"
            )
            self._loaded = True
            return

        supplier_rows: list[tuple[str, dict]] = []
        entity_rows: list[tuple[str, dict]] = []

        for year in self.years:
            try:
                contracts = await self._load_year(year)
                self._extract_index_rows(contracts, supplier_rows, entity_rows)
            except Exception as e:
                logger.warning(f"Failed to load contracts for {year}: {e}")

        try:
            await asyncio.to_thread(self._supplier_table.replace_all, supplier_rows)
            await asyncio.to_thread(self._entity_table.replace_all, entity_rows)
        except Exception as e:
            logger.warning(f"Failed to persist contracts to SQLite: {e}")

        self._loaded = True
        logger.info(
            f"Indexed contracts: {len(supplier_rows)} supplier entries, "
            f"{len(entity_rows)} entity entries"
        )

    async def _load_year(self, year: int) -> list[dict]:
        """Download and parse contract data for a given year.

        The SQLite DB is the only cache now — this method always
        downloads (callers are expected to check `is_fresh` before
        calling).
        """
        zip_url = await self._find_zip_url(year)
        if not zip_url:
            logger.warning(f"Could not find download URL for contracts {year}")
            return []

        async with self._client() as client:
            logger.info(f"Downloading contracts {year}...")
            resp = await client.get(zip_url)
            resp.raise_for_status()

            contracts = self._parse_zip(resp.content)
            logger.info(f"Loaded {len(contracts)} contracts for {year}")
            return contracts

    async def _find_zip_url(self, year: int) -> str | None:
        """Resolve the download URL for a year's contract ZIP."""
        # The dados.gov.pt resource URLs follow a pattern but include a timestamp
        # We'll try the dataset page to find the actual URL
        dataset_url = (
            "https://dados.gov.pt/api/1/datasets/"
            "contratos-publicos-portal-base-impic-contratos-de-2012-a-2026/"
        )
        try:
            async with self._client() as client:
                resp = await client.get(dataset_url)
                resp.raise_for_status()
                dataset = resp.json()

                for resource in dataset.get("resources", []):
                    title = resource.get("title", "").lower()
                    url = resource.get("url", "")
                    if f"contratos{year}" in title and url.endswith(".zip"):
                        return url
                    # Also match by URL pattern
                    if f"contratos{year}.zip" in url:
                        return url

        except Exception as e:
            logger.warning(f"Failed to resolve dataset URL: {e}")

        return None

    def _parse_zip(self, zip_bytes: bytes) -> list[dict]:
        """Extract contract records from a ZIP file containing CSV/JSON."""
        contracts = []
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                for name in zf.namelist():
                    if name.endswith(".csv"):
                        with zf.open(name) as f:
                            text = io.TextIOWrapper(f, encoding="utf-8-sig")
                            reader = csv.DictReader(text, delimiter=";")
                            for row in reader:
                                contracts.append(dict(row))
                    elif name.endswith(".json"):
                        with zf.open(name) as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                contracts.extend(data)
                            elif isinstance(data, dict) and "contracts" in data:
                                contracts.extend(data["contracts"])
        except Exception as e:
            logger.error(f"Failed to parse ZIP: {e}")
        return contracts

    def _extract_index_rows(
        self,
        contracts: list[dict],
        supplier_rows: list[tuple[str, dict]],
        entity_rows: list[tuple[str, dict]],
    ) -> None:
        """Flatten contracts into (nif, contract_dict) edges for each role.

        Same structure the old in-memory dict-of-lists held — we emit
        one row per (nif, contract) pairing so `get_by_nif` can reconstruct
        exactly what the dict lookup used to return.
        """
        for c in contracts:
            for nif in self._extract_nifs(c, "supplier"):
                supplier_rows.append((nif, c))
            for nif in self._extract_nifs(c, "entity"):
                entity_rows.append((nif, c))

    def _extract_nifs(self, contract: dict, role: str) -> list[str]:
        """Extract NIFs from a contract record.

        The IMPIC JSON format stores entities as lists of strings like:
          adjudicante: ["504595067 - Escola Profissional ..."]
          adjudicatarios: ["514181435 - GROWSKILLS ...", "504615947 - 1 - MEO ..."]
        We extract the leading 9-digit NIF from each entry.
        """
        nifs = []

        if role == "supplier":
            keys = ["adjudicatarios", "nifAdjudicatario", "supplier_nif"]
        else:
            keys = ["adjudicante", "nifEntidade", "entity_nif"]

        for key in keys:
            val = contract.get(key)
            if not val:
                continue

            # Handle list of "NIF - Name" strings (IMPIC JSON format)
            if isinstance(val, list):
                for entry in val:
                    m = re.match(r"^(\d{9})\b", str(entry).strip())
                    if m:
                        nifs.append(m.group(1))
            elif isinstance(val, str):
                # Handle pipe-separated or single NIF values
                for part in val.split("|"):
                    m = re.match(r"^(\d{9})\b", part.strip())
                    if m:
                        nifs.append(m.group(1))

            if nifs:
                break  # Found NIFs from this key, no need to try others

        return nifs

    def _to_contract(self, raw: dict) -> Contract:
        """Convert raw dict to Contract model."""

        def _get(keys: list[str], default: str = "") -> str:
            for k in keys:
                v = raw.get(k)
                if v:
                    return str(v).strip()
            return default

        def _get_float(keys: list[str]) -> float | None:
            for k in keys:
                v = raw.get(k)
                if v:
                    try:
                        return float(str(v).replace(",", ".").replace(" ", ""))
                    except ValueError:
                        continue
            return None

        # Parse "NIF - Name" list format from IMPIC JSON
        def _parse_nif_name_list(keys: list[str]) -> tuple[list[str], list[str]]:
            """Extract (names, nifs) from IMPIC 'NIF - Name' list fields."""
            names, nifs = [], []
            for k in keys:
                val = raw.get(k)
                if not val:
                    continue
                entries = val if isinstance(val, list) else [val]
                for entry in entries:
                    entry = str(entry).strip()
                    m = re.match(r"^(\d{9})\s*-\s*(.+)$", entry)
                    if m:
                        nifs.append(m.group(1))
                        names.append(m.group(2).strip())
                    else:
                        names.append(entry)
                if names or nifs:
                    break
            return names, nifs

        supplier_names, supplier_nifs = _parse_nif_name_list(
            ["adjudicatarios", "nomeAdjudicatario", "supplier"]
        )
        entity_names, entity_nifs = _parse_nif_name_list(
            ["adjudicante", "nomeEntidade", "entity"]
        )

        return Contract(
            id=_get(["idcontrato", "id", "ID"]),
            object_description=_get(
                ["objectoContrato", "object", "Objeto do Contrato", "Objeto"]
            ),
            contracting_entity=entity_names[0] if entity_names else "",
            contracting_nif=entity_nifs[0] if entity_nifs else "",
            suppliers=supplier_names,
            supplier_nifs=supplier_nifs,
            contract_price=_get_float(
                [
                    "precoContratual",
                    "contract_price",
                    "Preço Contratual",
                    "precoEfetivo",
                ]
            ),
            signing_date=_get(
                ["dataCelebracaoContrato", "signing_date", "Data de Celebração"]
            ),
            procedure_type=_get(
                [
                    "tipoProcedimento",
                    "procedure_type",
                    "Tipo de Procedimento",
                    "tipoprocedimento",
                ]
            ),
            year=int(y)
            if (y := _get(["anoPublicacao", "year", "Ano"])) and y.isdigit()
            else None,
        )

    async def search_by_nif(self, nif: str) -> dict[str, Any]:
        await self._ensure_loaded()

        as_supplier = await asyncio.to_thread(self._supplier_table.get_by_nif, nif)
        as_entity = await asyncio.to_thread(self._entity_table.get_by_nif, nif)

        # Deduplicate by contract id
        seen_ids: set[str] = set()
        all_contracts: list[Contract] = []

        for raw in as_supplier + as_entity:
            contract = self._to_contract(raw)
            if contract.id and contract.id not in seen_ids:
                seen_ids.add(contract.id)
                all_contracts.append(contract)
            elif not contract.id:
                all_contracts.append(contract)

        total_value = sum(c.contract_price or 0 for c in all_contracts)

        # Municipality aggregation: for contracts where this NIF was the
        # supplier (adjudicatário), bucket by the contracting municipality
        # so the UI can show "who this company sells to in the public sector".
        municipalities = self._aggregate_municipalities(as_supplier, nif)

        return {
            "contracts": all_contracts,
            "contracts_total_value": total_value,
            "municipality_contracts": municipalities,
        }

    # Strict municipality pattern: entry must START with "Município de " or
    # "Câmara Municipal de " (or "do"/"da"/"dos"/"das") right after the NIF
    # separator. This excludes "Serviços Intermunicipalizados", "Águas do
    # Município de X" (intermunicipal service companies), and other
    # inter-municipal entities that aren't city halls proper.
    _MUNICIPALITY_PATTERN = re.compile(
        r"^(\d{9})\s*-\s*"
        r"((?:Município|Câmara Municipal)\s+(?:de|do|da|dos|das)\s+.+?)"
        r"\s*$",
        re.IGNORECASE,
    )

    # Keep in sync with _to_contract._get_float — CSV rows use the
    # human-readable "Preço Contratual" column header, JSON rows use
    # the camelCase "precoContratual" / "precoEfetivo" keys.
    _PRICE_KEYS = (
        "precoContratual",
        "contract_price",
        "Preço Contratual",
        "precoEfetivo",
    )

    @classmethod
    def _price_of(cls, raw: dict) -> float:
        """Parse a contract's price, matching _to_contract's normalization."""
        for key in cls._PRICE_KEYS:
            v = raw.get(key)
            if v in (None, ""):
                continue
            try:
                return float(str(v).replace(",", ".").replace(" ", ""))
            except (ValueError, TypeError):
                continue
        return 0.0

    def _aggregate_municipalities(
        self, contracts_as_supplier: list[dict], supplier_nif: str
    ) -> list[dict]:
        """Bucket a supplier's contracts by the contracting municipality.

        A municipality is identified by `_MUNICIPALITY_PATTERN` — which
        requires the contracting entity string to start with "Município de X"
        or "Câmara Municipal de X" right after the leading NIF. This excludes
        inter-municipal service companies and similar entities that happen to
        contain "Municipal" in their name.

        Returns a list of {nif, name, contract_count, total_value} dicts
        sorted by total_value descending.
        """
        buckets: dict[str, dict[str, Any]] = {}
        seen_ids: set[str] = set()

        for raw in contracts_as_supplier:
            cid = str(raw.get("idcontrato") or raw.get("id") or "")
            if cid and cid in seen_ids:
                continue
            if cid:
                seen_ids.add(cid)

            # adjudicante is a list of "NIF - Name" strings in IMPIC format
            adjudicantes = raw.get("adjudicante") or []
            if not isinstance(adjudicantes, list):
                adjudicantes = [adjudicantes]

            price = self._price_of(raw)

            for entry in adjudicantes:
                entry_str = str(entry).strip()
                # Skip self-contracts (supplier = contracting entity)
                if entry_str.startswith(supplier_nif):
                    continue

                m = self._MUNICIPALITY_PATTERN.match(entry_str)
                if not m:
                    continue

                muni_nif = m.group(1)
                muni_name = m.group(2).strip()

                bucket = buckets.setdefault(
                    muni_nif,
                    {
                        "nif": muni_nif,
                        "name": muni_name,
                        "contract_count": 0,
                        "total_value": 0.0,
                    },
                )
                bucket["contract_count"] += 1
                bucket["total_value"] += price

        # Sort by total value desc
        out = sorted(
            buckets.values(),
            key=lambda b: b["total_value"],
            reverse=True,
        )
        return out
