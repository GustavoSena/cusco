from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Any

from ..models import Contract
from .base import DataSource

logger = logging.getLogger(__name__)

DADOS_GOV_BASE = "https://dados.gov.pt/s/resources/contratos-publicos-portal-base-impic-contratos-de-2012-a-2026"

# We'll load the most recent years for faster startup
DEFAULT_YEARS = [2026, 2025, 2024]

CACHE_DIR = Path(os.environ.get("CUSCO_CACHE_DIR", "/tmp/cusco_cache"))
CACHE_MAX_AGE_SECONDS = 24 * 3600  # 1 day


class ContractsSource(DataSource):
    name = "impic_contracts"

    def __init__(self, timeout: float = 120.0, years: list[int] | None = None):
        super().__init__(timeout=timeout)
        self.years = years or DEFAULT_YEARS
        self._contracts_by_supplier_nif: dict[str, list[dict]] = {}
        self._contracts_by_entity_nif: dict[str, list[dict]] = {}
        self._loaded = False
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async def _ensure_loaded(self) -> None:
        """Download and index contract data if not already loaded."""
        if self._loaded:
            return

        for year in self.years:
            try:
                data = await self._load_year(year)
                self._index_contracts(data)
            except Exception as e:
                logger.warning(f"Failed to load contracts for {year}: {e}")

        self._loaded = True
        total = sum(len(v) for v in self._contracts_by_supplier_nif.values())
        logger.info(
            f"Indexed contracts: {total} supplier entries, "
            f"{sum(len(v) for v in self._contracts_by_entity_nif.values())} entity entries"
        )

    async def _load_year(self, year: int) -> list[dict]:
        """Download and parse contract data for a given year."""
        cache_file = CACHE_DIR / f"contratos{year}.json"

        # Check cache
        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < CACHE_MAX_AGE_SECONDS:
                logger.info(f"Loading contracts {year} from cache")
                with open(cache_file) as f:
                    return json.load(f)

        # Download ZIP
        # The URL pattern from dados.gov.pt — we need to find the latest resource URL
        # For now, try the XLSX approach via the zip files
        zip_url = await self._find_zip_url(year)
        if not zip_url:
            logger.warning(f"Could not find download URL for contracts {year}")
            return []

        async with self._client() as client:
            logger.info(f"Downloading contracts {year}...")
            resp = await client.get(zip_url)
            resp.raise_for_status()

            contracts = self._parse_zip(resp.content)
            # Cache parsed data
            with open(cache_file, "w") as f:
                json.dump(contracts, f)
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

    def _index_contracts(self, contracts: list[dict]) -> None:
        """Build NIF-based indexes for fast lookup."""
        for c in contracts:
            # Index by supplier NIF(s)
            supplier_nifs = self._extract_nifs(c, "supplier")
            for nif in supplier_nifs:
                self._contracts_by_supplier_nif.setdefault(nif, []).append(c)

            # Index by contracting entity NIF
            entity_nifs = self._extract_nifs(c, "entity")
            for nif in entity_nifs:
                self._contracts_by_entity_nif.setdefault(nif, []).append(c)

    def _extract_nifs(self, contract: dict, role: str) -> list[str]:
        """Extract NIFs from a contract record.

        The IMPIC JSON format stores entities as lists of strings like:
          adjudicante: ["504595067 - Escola Profissional ..."]
          adjudicatarios: ["514181435 - GROWSKILLS ...", "504615947 - 1 - MEO ..."]
        We extract the leading 9-digit NIF from each entry.
        """
        import re

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
            import re
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

        as_supplier = self._contracts_by_supplier_nif.get(nif, [])
        as_entity = self._contracts_by_entity_nif.get(nif, [])

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

    @staticmethod
    def _price_of(raw: dict) -> float:
        """Parse a contract's price, matching _to_contract's normalization."""
        for key in ("precoContratual", "contract_price", "precoEfetivo"):
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
