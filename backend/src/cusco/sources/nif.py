from __future__ import annotations

import logging
from typing import Any

from ..models import CompanyInfo, EntityType
from .base import DataSource

logger = logging.getLogger(__name__)

PTDATA_BASE = "https://api.ptdata.org/v1"

TYPE_MAP = {
    "company": EntityType.COMPANY,
    "Pessoa Coletiva": EntityType.COMPANY,
    "Pessoa Singular": EntityType.INDIVIDUAL,
    "individual": EntityType.INDIVIDUAL,
}


class NifSource(DataSource):
    name = "ptdata_nif"

    async def search_by_nif(self, nif: str) -> dict[str, Any]:
        async with self._client() as client:
            resp = await client.get(f"{PTDATA_BASE}/fiscal/nif/{nif}")
            resp.raise_for_status()
            data = resp.json().get("data", {})

            raw_type = data.get("type_code") or data.get("type", "")
            entity_type = TYPE_MAP.get(raw_type, EntityType.UNKNOWN)

            return {
                "company": CompanyInfo(
                    nif=data.get("nif", nif),
                    name=None,  # NIF endpoint doesn't return name
                    entity_type=entity_type,
                    valid=data.get("valid", False),
                ),
            }
