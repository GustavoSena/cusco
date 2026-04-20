"""ptdata.org `/v1/companies/{nif}` source.

The upstream `NifSource` already wraps `/v1/fiscal/nif/{nif}` for NIF validation
and entity-type detection. This sibling source hits the richer
`/v1/companies/{nif}` endpoint, which returns SICAE-canonical name + address,
CAE industry classification codes, VIES VAT status, and aggregate public
contract stats.

Kept separate from `NifSource` to avoid cascading failures: if `/companies`
is slow or down, NIF validation still works. Graceful degradation — network
errors return `{"ptdata_company": None}` rather than raising, matching the
pattern used by every other source.
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import CAECode, PTDataCompany, PTDataSourceStatus
from .base import DataSource

logger = logging.getLogger(__name__)

PTDATA_BASE = "https://api.ptdata.org/v1"


class PTDataSource(DataSource):
    """Rich company profile from ptdata.org /v1/companies/{nif}."""

    name = "ptdata_company"

    def __init__(self, timeout: float = 15.0):
        super().__init__(timeout=timeout)

    async def search_by_nif(self, nif: str) -> dict[str, Any]:
        try:
            async with self._client() as client:
                resp = await client.get(f"{PTDATA_BASE}/companies/{nif}")
                resp.raise_for_status()
                payload = resp.json()
        except Exception as e:
            logger.warning(f"ptdata /companies lookup failed for {nif}: {e}")
            return {"ptdata_company": None}

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return {"ptdata_company": None}

        return {"ptdata_company": self._parse_company(data, nif)}

    def _parse_company(self, data: dict, nif: str) -> PTDataCompany:
        cae_codes = [
            CAECode(
                code=str(c.get("code") or ""),
                description=str(c.get("description") or ""),
                type=str(c.get("type") or ""),
            )
            for c in (data.get("cae_codes") or [])
            if isinstance(c, dict)
        ]

        source_checks = [
            PTDataSourceStatus(
                id=str(s.get("id") or ""),
                name=str(s.get("name") or ""),
                status=str(s.get("status") or ""),
                records=s.get("records") if isinstance(s.get("records"), int) else None,
            )
            for s in (data.get("sources") or [])
            if isinstance(s, dict)
        ]

        public_contracts = data.get("public_contracts") or {}
        if not isinstance(public_contracts, dict):
            public_contracts = {}

        pc_total = public_contracts.get("total")
        pc_value = public_contracts.get("total_value")

        return PTDataCompany(
            nif=str(data.get("nif") or nif),
            name=str(data.get("name") or ""),
            sicae_name=str(data.get("sicae_name") or ""),
            address=str(data.get("address") or ""),
            type_code=str(data.get("type_code") or ""),
            vat_active=bool(data.get("vat_active") or False),
            cae_codes=cae_codes,
            source_checks=source_checks,
            public_contracts_total=pc_total if isinstance(pc_total, int) else None,
            public_contracts_value=(
                float(pc_value) if isinstance(pc_value, (int, float)) else None
            ),
        )
