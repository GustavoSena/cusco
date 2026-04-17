"""GLEIF (Global Legal Entity Identifier Foundation) API source.

Free, unauthenticated API that returns rich company metadata for entities
with an LEI (Legal Entity Identifier). Primarily covers financial institutions
and companies active in capital markets, but also many larger Portuguese companies.

Provides: legal name, registered address, headquarters address, entity status,
LEI code, legal form, jurisdiction, registration authority, parent relationships.
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import GroupMember, LEIRecord
from .base import DataSource

logger = logging.getLogger(__name__)

GLEIF_API_BASE = "https://api.gleif.org/api/v1"

# Max pages of direct-children to fetch (page size 100 → up to 200 children).
MAX_CHILDREN_PAGES = 2
CHILDREN_PAGE_SIZE = 100


class GleifSource(DataSource):
    """GLEIF LEI record lookup by NIF."""

    name = "gleif"

    def __init__(self, timeout: float = 15.0):
        super().__init__(timeout=timeout)

    async def search_by_nif(self, nif: str) -> dict[str, Any]:
        async with self._client() as client:
            resp = await client.get(
                f"{GLEIF_API_BASE}/lei-records",
                params={
                    "filter[entity.registeredAs]": nif,
                    "filter[entity.legalAddress.country]": "PT",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            records = data.get("data", [])
            if not records:
                return {"lei_record": None}

            # Take the first (most relevant) match
            record = self._parse_record(records[0])
            return {"lei_record": record}

    async def search_by_name(self, name: str) -> dict[str, Any]:
        """Search GLEIF by company name (Portuguese entities only)."""
        async with self._client() as client:
            resp = await client.get(
                f"{GLEIF_API_BASE}/lei-records",
                params={
                    "filter[entity.legalName]": name,
                    "filter[entity.legalAddress.country]": "PT",
                    "page[size]": "20",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            records = data.get("data", [])
            return {
                "lei_records": [self._parse_record(r) for r in records],
                "total_matches": data.get("meta", {}).get("pagination", {}).get("total", len(records)),
            }

    def _parse_record(self, raw: dict) -> LEIRecord:
        """Parse a GLEIF API record into our LEIRecord model."""
        attrs = raw.get("attributes", {})
        entity = attrs.get("entity", {})
        registration = attrs.get("registration", {})

        # Legal address
        legal_addr = entity.get("legalAddress", {})
        address_lines = legal_addr.get("addressLines", [])
        address = ", ".join(address_lines) if address_lines else ""

        # Headquarters address (may differ from legal address)
        hq_addr = entity.get("headquartersAddress", {})
        hq_lines = hq_addr.get("addressLines", [])
        hq_address = ", ".join(hq_lines) if hq_lines else ""

        # Other names (trade names, previous names)
        other_names = []
        for name_entry in entity.get("otherNames", []):
            n = name_entry.get("name", "")
            if n:
                other_names.append(n)

        return LEIRecord(
            lei=attrs.get("lei") or "",
            legal_name=(entity.get("legalName") or {}).get("name") or "",
            other_names=other_names,
            legal_address=address,
            legal_city=legal_addr.get("city") or "",
            legal_region=legal_addr.get("region") or "",
            legal_country=legal_addr.get("country") or "",
            legal_postal_code=legal_addr.get("postalCode") or "",
            headquarters_address=hq_address,
            headquarters_city=hq_addr.get("city") or "",
            headquarters_country=hq_addr.get("country") or "",
            registered_as=entity.get("registeredAs") or "",
            jurisdiction=entity.get("jurisdiction") or "",
            entity_status=entity.get("status") or "",
            entity_category=entity.get("category") or "",
            legal_form_code=(entity.get("legalForm") or {}).get("id") or "",
            registration_status=registration.get("status") or "",
            initial_registration_date=registration.get("initialRegistrationDate") or "",
            last_update_date=registration.get("lastUpdateDate") or "",
            next_renewal_date=registration.get("nextRenewalDate") or "",
        )

    # -- Corporate group relationships ------------------------------------
    async def get_corporate_group(self, lei: str) -> dict[str, Any]:
        """Fetch direct children and direct parent for an LEI.

        Uses GLEIF's `/lei-records/{lei}/direct-children` (paginated) and
        `/lei-records/{lei}/direct-parent` (404 → no parent). Children are
        capped at MAX_CHILDREN_PAGES * CHILDREN_PAGE_SIZE entries; `has_more`
        is set when truncated.

        Returns a dict shaped like:
            {
                "direct_parent": GroupMember | None,
                "direct_children": list[GroupMember],
                "total_children": int,
                "has_more_children": bool,
            }
        """
        if not lei:
            return {
                "direct_parent": None,
                "direct_children": [],
                "total_children": 0,
                "has_more_children": False,
            }

        children: list[GroupMember] = []
        total_children = 0
        has_more = False

        async with self._client() as client:
            # Direct parent (may 404)
            parent: GroupMember | None = None
            try:
                resp = await client.get(
                    f"{GLEIF_API_BASE}/lei-records/{lei}/direct-parent"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    raw = data.get("data")
                    if raw:
                        parent = self._parse_group_member(raw, "parent")
                elif resp.status_code != 404:
                    logger.warning(
                        f"GLEIF direct-parent returned {resp.status_code} for {lei}"
                    )
            except Exception as e:
                logger.warning(f"GLEIF direct-parent fetch failed for {lei}: {e}")

            # Direct children (paginated)
            for page in range(1, MAX_CHILDREN_PAGES + 1):
                try:
                    resp = await client.get(
                        f"{GLEIF_API_BASE}/lei-records/{lei}/direct-children",
                        params={
                            "page[size]": str(CHILDREN_PAGE_SIZE),
                            "page[number]": str(page),
                        },
                    )
                    if resp.status_code == 404:
                        break
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    logger.warning(
                        f"GLEIF direct-children fetch failed for {lei} p{page}: {e}"
                    )
                    break

                page_items = data.get("data", []) or []
                for raw in page_items:
                    children.append(self._parse_group_member(raw, "child"))

                pagination = (data.get("meta") or {}).get("pagination") or {}
                total_children = int(pagination.get("total") or len(children))
                total_pages = int(pagination.get("totalPages") or 0)

                if total_pages and page >= total_pages:
                    break
                if not page_items:
                    break

            if total_children > len(children):
                has_more = True

        return {
            "direct_parent": parent,
            "direct_children": children,
            "total_children": total_children or len(children),
            "has_more_children": has_more,
        }

    def _parse_group_member(self, raw: dict, relationship: str) -> GroupMember:
        """Extract minimal identity info for a related LEI record."""
        attrs = raw.get("attributes", {}) or {}
        entity = attrs.get("entity", {}) or {}
        legal_name_obj = entity.get("legalName") or {}
        legal_addr = entity.get("legalAddress") or {}

        return GroupMember(
            nif=str(entity.get("registeredAs") or "").strip(),
            name=str(legal_name_obj.get("name") or "").strip(),
            lei=str(attrs.get("lei") or "").strip(),
            country=str(legal_addr.get("country") or "").strip(),
            entity_status=str(entity.get("status") or "").strip(),
            relationship=relationship,
        )
