"""Segurança Social public procedures source.

Fetches public recruitment/mobility procedures from the Social Security portal.
While not directly company insolvency data, this provides structured data about
public sector entities and their personnel movements — useful for mapping
organizational structure and connecting to entity intelligence.

API endpoint: GET https://www.seg-social.pt/ptss/rest/public/pssd/procedures
Returns: procedures with organism info, career types, publication dates, documents.
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import SegSocialProcedure, SegSocialOrganism
from .base import DataSource

logger = logging.getLogger(__name__)

BASE_URL = "https://www.seg-social.pt/ptss/rest/public/pssd/procedures"

# We need to first load the page to get a session cookie
PAGE_URL = "https://www.seg-social.pt/ptss/pssd/procedimentos-concursais"


class SegSocialSource(DataSource):
    """Segurança Social public procedures API."""

    name = "seg_social"

    def __init__(self, timeout: float = 20.0):
        super().__init__(timeout=timeout)

    async def _fetch_procedures(self, proc_type: str = "PROCEDURE") -> list[dict]:
        """Fetch all procedures of a given type."""
        async with self._client() as client:
            # First load the HTML page purely to pick up the session
            # cookie (fvcc) that the JSON endpoint requires. We throw
            # the response away — don't assign to a named variable
            # (ruff F841) and don't `raise_for_status` since a 403/500
            # still sets the cookie we need.
            await client.get(
                PAGE_URL,
                headers={
                    "Accept": "text/html",
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )

            # Now fetch the JSON API
            resp = await client.get(
                BASE_URL,
                params={"type": proc_type},
                headers={
                    "Accept": "application/json",
                    "Referer": PAGE_URL,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list):
                return data
            return []

    async def search_by_nif(self, nif: str) -> dict[str, Any]:
        """Seg Social has no NIF filter — return empty and let
        `_enrich_seg_social` in main.py resolve matches by company name.

        Previously this returned EVERY procedure from the API for every
        NIF search, because the loop `matching.append(raw)` had no guard.
        The card on the frontend then displayed ~200 unrelated
        procedures for every company — loudly wrong for private
        companies, misleading for public ones.

        Returning empty here (instead of reusing `search_by_name`
        blindly with the NIF) keeps the source's status reporting
        intact without leaking unfiltered data into the report."""
        return {
            "seg_social_procedures": [],
            "seg_social_organisms": [],
        }

    async def search_by_company_name(
        self, name: str, acronym: str | None = None
    ) -> dict[str, Any]:
        """Filter procedures whose organism name/acronym matches the company.

        Called as a name-based enrichment step AFTER entities/gleif/ptdata
        have filled in `report.company.name`. Matching is intentionally
        strict — substring match on the FULL name (not a token), plus
        optional acronym match — because Seg Social organisms are
        public-sector entities (ministries, universities, municipal
        councils) and we don't want e.g. searching "EDP" to accidentally
        match "Escola Dr. Pedro..." via a shared prefix.
        """
        query = (name or "").strip().lower()
        acr = (acronym or "").strip().lower() if acronym else ""
        if len(query) < 3:
            # Short names produce too many false positives in substring
            # matching; require a real name to avoid leaking noise.
            return {"seg_social_procedures": [], "seg_social_organisms": []}

        try:
            all_procs = await self._fetch_procedures()
        except Exception as e:  # noqa: BLE001 - enrichment is best-effort
            logger.warning(f"Seg Social fetch failed: {e}")
            return {"seg_social_procedures": [], "seg_social_organisms": []}

        # Also fetch mobility procedures — same endpoint, different type
        try:
            mobility_procs = await self._fetch_procedures("MOBILITY")
            all_procs.extend(mobility_procs)
        except Exception:  # noqa: BLE001 - MOBILITY endpoint may not exist
            pass

        matching: list[dict] = []
        for raw in all_procs:
            organism = raw.get("organism", {}) or {}
            org_name = str(organism.get("name", "")).lower()
            org_acronym = str(organism.get("acronym", "")).lower()

            # Match on full-name substring (company name contained in
            # organism name, or vice-versa — public entities sometimes
            # have a longer formal name than the user's search). Acronym
            # match requires EXACT equality to avoid matching 3-letter
            # fragments inside unrelated strings.
            name_match = (
                (query in org_name and org_name)
                or (org_name and org_name in query)
            )
            acronym_match = bool(acr) and acr == org_acronym
            if name_match or acronym_match:
                matching.append(raw)

        procedures = [self._to_procedure(p) for p in matching]

        # Group by organism — same logic as before, but only for the
        # filtered subset so orphaned organism badges don't leak.
        organisms: dict[str, SegSocialOrganism] = {}
        for proc in procedures:
            if proc.organism_name and proc.organism_id:
                if proc.organism_id not in organisms:
                    organisms[proc.organism_id] = SegSocialOrganism(
                        id=proc.organism_id,
                        name=proc.organism_name,
                        acronym=proc.organism_acronym,
                        procedure_count=0,
                    )
                organisms[proc.organism_id].procedure_count += 1

        return {
            "seg_social_procedures": procedures,
            "seg_social_organisms": list(organisms.values()),
        }

    async def search_by_name(self, name: str) -> dict[str, Any]:
        """Search procedures by organism or procedure name."""
        all_procs = await self._fetch_procedures()

        query = name.lower().strip()
        matching = []

        for raw in all_procs:
            organism = raw.get("organism", {})
            org_name = str(organism.get("name", "")).lower()
            org_acronym = str(organism.get("acronym", "")).lower()
            proc_title = str(raw.get("title", "")).lower()

            if (
                query in org_name
                or query in org_acronym
                or query in proc_title
            ):
                matching.append(raw)

        procedures = [self._to_procedure(p) for p in matching]
        return {
            "seg_social_procedures": procedures,
            "total_matches": len(procedures),
        }

    def _to_procedure(self, raw: dict) -> SegSocialProcedure:
        """Convert raw API record to SegSocialProcedure model."""
        organism = raw.get("organism", {})

        # Parse publication date from epoch ms
        pub_date_ms = raw.get("publicationDate")
        pub_date = ""
        if pub_date_ms:
            try:
                from datetime import datetime, timezone

                dt = datetime.fromtimestamp(pub_date_ms / 1000, tz=timezone.utc)
                pub_date = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError, OSError):
                pass

        # Parse expiration date
        exp_date_ms = raw.get("expDate")
        exp_date = ""
        if exp_date_ms:
            try:
                from datetime import datetime, timezone

                dt = datetime.fromtimestamp(exp_date_ms / 1000, tz=timezone.utc)
                exp_date = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError, OSError):
                pass

        # Extract document URLs
        documents = []
        for doc in raw.get("documents", []):
            doc_url = doc.get("url", "")
            doc_title = doc.get("title", doc.get("name", ""))
            if doc_url:
                documents.append({"title": doc_title, "url": doc_url})

        return SegSocialProcedure(
            code=str(raw.get("code", "")),
            title=str(raw.get("title", "")),
            variant=str(raw.get("variant", "")),
            scope=str(raw.get("scope", "")),
            procedure_type=str(raw.get("type", "")),
            career=str(raw.get("career", "")),
            service=str(raw.get("service", "")),
            publication_date=pub_date,
            expiration_date=exp_date,
            organism_id=str(organism.get("id", "")),
            organism_name=str(organism.get("name", "")),
            organism_acronym=str(organism.get("acronym", "")),
            documents=documents,
        )
