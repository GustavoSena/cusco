"""IMPIC entity registry from dados.gov.pt.

Downloads the bulk entidades.json (~47MB) on a 24h TTL and persists it in
SQLite (via :mod:`cusco.storage`) for NIF- and name-based lookup.

Provides:
- Company name + country enrichment for any NIF
- Name-to-NIF substring search
- Aggregate contract stats (total contracts, total value as supplier/entity)

Storage shape:
- `entities` bulk table: (nif, entity_dict_json) — one row per entity
- `entities_by_name` index table: (name_lower, nif) for `search_by_name`
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..models import EntityProfile
from ..storage import BulkTable, NameIndexTable
from .base import DataSource

logger = logging.getLogger(__name__)

DATASET_API_URL = (
    "https://dados.gov.pt/api/1/datasets/"
    "contratos-publicos-portal-base-impic-entidades/"
)

CACHE_MAX_AGE_SECONDS = 24 * 3600  # 1 day


class EntitiesSource(DataSource):
    """IMPIC entity registry — bulk download from dados.gov.pt."""

    name = "impic_entities"

    def __init__(self, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        # NIF-keyed payload table + a small (name_lower, nif) index for
        # substring name search. Both are rebuilt together in `_do_load`.
        self._table = BulkTable("entities")
        self._name_index = NameIndexTable("entities_by_name")
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        """Idempotent load — serialized via `_load_once` so concurrent
        first queries don't each re-download + re-parse the dataset."""
        await self._load_once(self._do_load, lambda: self._loaded)

    async def _do_load(self) -> None:
        table_fresh = await asyncio.to_thread(
            self._table.is_fresh, CACHE_MAX_AGE_SECONDS
        )
        name_fresh = await asyncio.to_thread(
            self._name_index.is_fresh, CACHE_MAX_AGE_SECONDS
        )
        if table_fresh and name_fresh:
            row_count = await asyncio.to_thread(self._table.row_count)
            logger.info(
                f"IMPIC entities: SQLite fresh — {row_count} entities "
                "(skipping download)"
            )
            self._loaded = True
            return

        try:
            data = await self._load_entities()
            await self._persist_entities(data)
        except Exception as e:
            logger.warning(f"Failed to load IMPIC entities: {e}")
        self._loaded = True

    async def _load_entities(self) -> list[dict]:
        # Resolve download URL from the dataset API
        url = await self._find_json_url()
        if not url:
            logger.warning("Could not find IMPIC entities download URL")
            return []

        async with self._client() as client:
            logger.info("Downloading IMPIC entities...")
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, dict):
                # Might be wrapped: {"entities": [...]} or similar
                for key in ("entities", "entidades", "data", "results"):
                    if key in data and isinstance(data[key], list):
                        data = data[key]
                        break
                else:
                    # If it's a dict but none of those keys, it's not what we expect
                    if not isinstance(data, list):
                        logger.warning(
                            f"Unexpected IMPIC entities format: {type(data)}"
                        )
                        return []

            logger.info(f"Loaded {len(data)} IMPIC entities")
            return data

    async def _find_json_url(self) -> str | None:
        """Resolve the JSON download URL from the dados.gov.pt dataset API."""
        try:
            async with self._client() as client:
                resp = await client.get(DATASET_API_URL)
                resp.raise_for_status()
                dataset = resp.json()

                for resource in dataset.get("resources", []):
                    title = resource.get("title", "").lower()
                    url = resource.get("url", "")
                    if "entidades" in title and url.endswith(".json"):
                        return url
                    if "entidades.json" in url:
                        return url
        except Exception as e:
            logger.warning(f"Failed to resolve IMPIC entities URL: {e}")
        return None

    async def _persist_entities(self, entities: list[dict]) -> None:
        """Write entities + name index to SQLite.

        We build the two (key, row) lists up-front and then hand both off
        to `BulkTable.replace_all` / `NameIndexTable.replace_all`. Each
        table is rewritten atomically inside its own transaction.
        """
        nif_rows: list[tuple[str, dict]] = []
        name_rows: list[tuple[str, str]] = []

        for entity in entities:
            nif = str(entity.get("nifEntidade", "")).strip()
            name = str(entity.get("desigEntidade", "")).strip()

            if nif and nif != "-":
                nif_rows.append((nif, entity))
                if name:
                    name_rows.append((name.lower(), nif))

        try:
            await asyncio.to_thread(self._table.replace_all, nif_rows)
            await asyncio.to_thread(self._name_index.replace_all, name_rows)
        except Exception as e:
            logger.warning(f"Failed to persist IMPIC entities to SQLite: {e}")
            return

        logger.info(
            f"Indexed IMPIC entities: {len(nif_rows)} by NIF, "
            f"{len(name_rows)} name-indexed rows"
        )

    def _to_profile(self, raw: dict) -> EntityProfile:
        """Convert raw entity dict to EntityProfile model."""

        def _safe_float(val: Any) -> float | None:
            if val is None:
                return None
            try:
                return float(str(val).replace(",", ".").replace(" ", ""))
            except (ValueError, TypeError):
                return None

        def _safe_int(val: Any) -> int | None:
            if val is None:
                return None
            try:
                return int(float(str(val).replace(",", ".").replace(" ", "")))
            except (ValueError, TypeError):
                return None

        return EntityProfile(
            nif=str(raw.get("nifEntidade", "")).strip(),
            name=str(raw.get("desigEntidade", "")).strip(),
            country=str(raw.get("descPais", "")).strip() or None,
            country_code=str(raw.get("AliasPais", "")).strip() or None,
            total_contracts=_safe_int(raw.get("numContratos")),
            times_as_supplier=_safe_int(raw.get("totAdjudicatario")),
            total_value_as_supplier=_safe_float(raw.get("totValorContratIni")),
            times_as_entity=_safe_int(raw.get("totAdjudicante")),
            total_value_as_entity=_safe_float(
                raw.get("totAdjudicanteValorContratIni")
            ),
        )

    async def search_by_nif(self, nif: str) -> dict[str, Any]:
        await self._ensure_loaded()

        rows = await asyncio.to_thread(self._table.get_by_nif, nif)
        if not rows:
            return {"entity_profile": None}

        return {"entity_profile": self._to_profile(rows[0])}

    async def search_by_name(self, name: str) -> dict[str, Any]:
        """Search entities by name (case-insensitive substring match).

        Returns top 20 matches; exact hits come before substring hits.
        """
        await self._ensure_loaded()

        query = name.lower().strip()
        if not query or len(query) < 2:
            return {"entity_profiles": [], "total_matches": 0}

        # Pull up to 100 candidate NIFs from the name index (exact first),
        # then hydrate each one from the payload table. `search_nifs_by_substring`
        # already preserves the exact-first ordering so we can just walk it.
        nifs = await asyncio.to_thread(
            self._name_index.search_nifs_by_substring, query, 100
        )

        results: list[EntityProfile] = []
        for nif in nifs:
            rows = await asyncio.to_thread(self._table.get_by_nif, nif)
            for raw in rows:
                results.append(self._to_profile(raw))
                if len(results) >= 100:
                    break
            if len(results) >= 100:
                break

        return {
            "entity_profiles": results[:20],
            "total_matches": len(results),
        }
