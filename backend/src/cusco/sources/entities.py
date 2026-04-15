"""IMPIC entity registry from dados.gov.pt.

Downloads the bulk entidades.json (~47MB) and indexes by NIF and name.
Provides:
- Company name + country enrichment for any NIF
- Name-to-NIF fuzzy search
- Aggregate contract stats (total contracts, total value as supplier/entity)
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from ..models import EntityProfile
from .base import DataSource

logger = logging.getLogger(__name__)

DATASET_API_URL = (
    "https://dados.gov.pt/api/1/datasets/"
    "contratos-publicos-portal-base-impic-entidades/"
)

CACHE_DIR = Path(os.environ.get("CUSCO_CACHE_DIR", "/tmp/cusco_cache"))
CACHE_MAX_AGE_SECONDS = 24 * 3600  # 1 day


class EntitiesSource(DataSource):
    """IMPIC entity registry — bulk download from dados.gov.pt."""

    name = "impic_entities"

    def __init__(self, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self._by_nif: dict[str, dict] = {}
        self._by_name: dict[str, list[dict]] = {}  # lowercase name -> entities
        self._loaded = False
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        try:
            data = await self._load_entities()
            self._index_entities(data)
        except Exception as e:
            logger.warning(f"Failed to load IMPIC entities: {e}")
        self._loaded = True

    async def _load_entities(self) -> list[dict]:
        cache_file = CACHE_DIR / "entidades.json"

        # Check cache
        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < CACHE_MAX_AGE_SECONDS:
                logger.info("Loading IMPIC entities from cache")
                with open(cache_file) as f:
                    return json.load(f)

        # Resolve download URL from the dataset API
        url = await self._find_json_url()
        if not url:
            logger.warning("Could not find IMPIC entities download URL")
            # Fall back to stale cache
            if cache_file.exists():
                with open(cache_file) as f:
                    return json.load(f)
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

            # Cache the raw data
            with open(cache_file, "w") as f:
                json.dump(data, f)

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

    def _index_entities(self, entities: list[dict]) -> None:
        """Build NIF and name indexes for fast lookup."""
        for entity in entities:
            nif = str(entity.get("nifEntidade", "")).strip()
            name = str(entity.get("desigEntidade", "")).strip()

            if nif and nif != "-":
                self._by_nif[nif] = entity

            if name:
                key = name.lower()
                self._by_name.setdefault(key, []).append(entity)

        logger.info(
            f"Indexed IMPIC entities: {len(self._by_nif)} by NIF, "
            f"{len(self._by_name)} unique names"
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

        raw = self._by_nif.get(nif)
        if not raw:
            return {"entity_profile": None}

        return {"entity_profile": self._to_profile(raw)}

    async def search_by_name(self, name: str) -> dict[str, Any]:
        """Search entities by name (case-insensitive substring match).

        Returns top 20 matches, exact matches first, then substring matches.
        """
        await self._ensure_loaded()

        query = name.lower().strip()
        if not query or len(query) < 2:
            return {"entity_profiles": [], "total_matches": 0}

        exact: list[EntityProfile] = []
        partial: list[EntityProfile] = []

        # Exact match first
        if query in self._by_name:
            for raw in self._by_name[query]:
                exact.append(self._to_profile(raw))

        # Substring match across all names (capped for performance)
        matches_checked = 0
        for stored_name, entities in self._by_name.items():
            if stored_name == query:
                continue  # Already handled
            if query in stored_name:
                for raw in entities:
                    partial.append(self._to_profile(raw))
                    if len(partial) >= 100:
                        break
            matches_checked += 1
            if len(partial) >= 100:
                break

        results = exact + partial
        return {
            "entity_profiles": results[:20],
            "total_matches": len(results),
        }
