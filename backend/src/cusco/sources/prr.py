"""PRR (Plano de Recuperação e Resiliência) data source.

Downloads two bulk XLSX datasets from dados.gov.pt:

- PRR Entidades (~750K rows): funding records per entity, tracked by NIF. Each
  row records a project/entity pairing with contracted and paid values, role
  (beneficiário final, intermediário, etc.), CAE code and municipality.
- PRR Contratos (~12K rows): public contracts signed under PRR funding, with
  contracting authority / supplier roles.

Both are loaded once, parsed, cached as JSON in `CUSCO_CACHE_DIR`, and indexed
by NIF in-memory (24h TTL). Pattern mirrors `contracts.py` / `entities.py`.
"""

from __future__ import annotations

import io
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from ..models import PRRContract, PRRFunding
from .base import DataSource

logger = logging.getLogger(__name__)

DATASET_API_ENTIDADES = (
    "https://dados.gov.pt/api/1/datasets/"
    "dataset-estrutura-de-missao-prr-entidades-1/"
)
DATASET_API_CONTRATOS = (
    "https://dados.gov.pt/api/1/datasets/"
    "dataset-estrutura-de-missao-prr-entidades-contratos-publicos/"
)

CACHE_DIR = Path(os.environ.get("CUSCO_CACHE_DIR", "/tmp/cusco_cache"))
CACHE_MAX_AGE_SECONDS = 24 * 3600  # 1 day


def _safe_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace(",", ".").replace(" ", ""))
    except (ValueError, TypeError):
        return None


def _normalize_nif(val: Any) -> str:
    """Normalize NIF-like values: strip, remove PT prefix, keep digits as-is."""
    if val is None:
        return ""
    s = str(val).strip()
    if s.upper().startswith("PT"):
        s = s[2:].strip()
    # Some NIFs come as floats (openpyxl quirk): "514181435.0"
    if s.endswith(".0"):
        s = s[:-2]
    return s


class PRRSource(DataSource):
    """PRR entity funding + contracts from dados.gov.pt."""

    name = "prr"

    def __init__(self, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self._fundings_by_nif: dict[str, list[dict]] = {}
        self._contracts_by_nif: dict[str, list[dict]] = {}
        self._loaded = False
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return

        try:
            fundings = await self._load_fundings()
            self._index_fundings(fundings)
        except Exception as e:
            logger.warning(f"Failed to load PRR entidades: {e}")

        try:
            contracts = await self._load_contracts()
            self._index_contracts(contracts)
        except Exception as e:
            logger.warning(f"Failed to load PRR contratos: {e}")

        self._loaded = True
        logger.info(
            f"Indexed PRR: {len(self._fundings_by_nif)} NIFs with fundings, "
            f"{len(self._contracts_by_nif)} NIFs with contracts"
        )

    # -- Dataset A: Entidades ----------------------------------------------
    async def _load_fundings(self) -> list[dict]:
        cache_file = CACHE_DIR / "prr_entidades.json"

        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < CACHE_MAX_AGE_SECONDS:
                logger.info("Loading PRR entidades from cache")
                with open(cache_file) as f:
                    return json.load(f)

        url = await self._find_resource_url(DATASET_API_ENTIDADES, "entidades")
        if not url:
            logger.warning("Could not find PRR entidades download URL")
            if cache_file.exists():
                with open(cache_file) as f:
                    return json.load(f)
            return []

        async with self._client() as client:
            logger.info(f"Downloading PRR entidades from {url}...")
            resp = await client.get(url)
            resp.raise_for_status()
            rows = self._parse_prr_entidades_xlsx(resp.content)

            with open(cache_file, "w") as f:
                json.dump(rows, f)
            logger.info(f"Loaded {len(rows)} PRR entidades rows")
            return rows

    def _parse_prr_entidades_xlsx(self, xlsx_bytes: bytes) -> list[dict]:
        """Parse the PRR entidades XLSX into list[dict]."""
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
        ws = wb.active
        if ws is None:
            return []

        rows_iter = ws.iter_rows(values_only=True)
        try:
            headers = [str(h).strip() if h is not None else "" for h in next(rows_iter)]
        except StopIteration:
            return []

        out: list[dict] = []
        for row in rows_iter:
            if row is None:
                continue
            record = {}
            for idx, header in enumerate(headers):
                if not header:
                    continue
                value = row[idx] if idx < len(row) else None
                record[header] = value
            if any(v not in (None, "") for v in record.values()):
                out.append(record)

        wb.close()
        return out

    def _index_fundings(self, rows: list[dict]) -> None:
        for row in rows:
            nif = _normalize_nif(row.get("nif_entidade"))
            if not nif:
                continue
            self._fundings_by_nif.setdefault(nif, []).append(row)

    def _to_funding(self, raw: dict) -> PRRFunding:
        return PRRFunding(
            project_code=str(raw.get("cd_projeto") or "").strip(),
            entity_name=str(raw.get("ds_entidade") or "").strip(),
            role=str(raw.get("papel_entidade") or "").strip(),
            cae_code=str(raw.get("atividade_economica") or "").strip(),
            municipality=str(raw.get("localizacao_sede") or "").strip(),
            value_contracted=_safe_float(raw.get("valor_contratado")),
            value_paid=_safe_float(raw.get("valor_pago")),
            reference_date=str(raw.get("dt_referencia") or "").strip(),
        )

    # -- Dataset B: Contratos ----------------------------------------------
    async def _load_contracts(self) -> list[dict]:
        cache_file = CACHE_DIR / "prr_contratos.json"

        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < CACHE_MAX_AGE_SECONDS:
                logger.info("Loading PRR contratos from cache")
                with open(cache_file) as f:
                    return json.load(f)

        url = await self._find_resource_url(
            DATASET_API_CONTRATOS, "contratos"
        )
        if not url:
            logger.warning("Could not find PRR contratos download URL")
            if cache_file.exists():
                with open(cache_file) as f:
                    return json.load(f)
            return []

        async with self._client() as client:
            logger.info(f"Downloading PRR contratos from {url}...")
            resp = await client.get(url)
            resp.raise_for_status()
            rows = self._parse_prr_contratos_xlsx(resp.content)

            with open(cache_file, "w") as f:
                json.dump(rows, f)
            logger.info(f"Loaded {len(rows)} PRR contratos rows")
            return rows

    def _parse_prr_contratos_xlsx(self, xlsx_bytes: bytes) -> list[dict]:
        # Same shape as the entidades parser — reuse.
        return self._parse_prr_entidades_xlsx(xlsx_bytes)

    def _index_contracts(self, rows: list[dict]) -> None:
        for row in rows:
            nif = _normalize_nif(row.get("cd_entidade"))
            if not nif:
                continue
            self._contracts_by_nif.setdefault(nif, []).append(row)

    def _to_contract(self, raw: dict) -> PRRContract:
        return PRRContract(
            contract_code=str(raw.get("cd_contrato") or "").strip(),
            description=str(raw.get("ds_contrato") or "").strip(),
            entity_name=str(raw.get("ds_entidade") or "").strip(),
            role=str(raw.get("ds_papel_entidade_contrato") or "").strip(),
            value=_safe_float(raw.get("valor_contrato")),
            reference_date=str(raw.get("dt_referencia") or "").strip(),
        )

    # -- Resource URL resolution -------------------------------------------
    async def _find_resource_url(self, dataset_api: str, hint: str) -> str | None:
        """Resolve the XLSX download URL from a dados.gov.pt dataset API."""
        try:
            async with self._client() as client:
                resp = await client.get(dataset_api)
                resp.raise_for_status()
                dataset = resp.json()

                hint_l = hint.lower()
                for resource in dataset.get("resources", []):
                    title = (resource.get("title") or "").lower()
                    url = resource.get("url") or ""
                    url_l = url.lower()
                    if not url:
                        continue
                    if url_l.endswith(".xlsx") and (
                        hint_l in title or hint_l in url_l
                    ):
                        return url
                # Fall back to the first xlsx resource if no hint match
                for resource in dataset.get("resources", []):
                    url = resource.get("url") or ""
                    if url.lower().endswith(".xlsx"):
                        return url
        except Exception as e:
            logger.warning(f"Failed to resolve PRR dataset URL ({dataset_api}): {e}")
        return None

    # -- Public API --------------------------------------------------------
    async def search_by_nif(self, nif: str) -> dict[str, Any]:
        await self._ensure_loaded()
        nif = _normalize_nif(nif)

        raw_fundings = self._fundings_by_nif.get(nif, [])
        raw_contracts = self._contracts_by_nif.get(nif, [])

        fundings = [self._to_funding(r) for r in raw_fundings]
        contracts = [self._to_contract(r) for r in raw_contracts]

        total_contracted = sum(f.value_contracted or 0 for f in fundings)
        total_paid = sum(f.value_paid or 0 for f in fundings)

        return {
            "prr_fundings": fundings,
            "prr_contracts": contracts,
            "has_prr_funding": bool(fundings),
            "prr_total_contracted": total_contracted,
            "prr_total_paid": total_paid,
        }
