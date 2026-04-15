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
            # First load the HTML page to get session cookie (fvcc)
            page_resp = await client.get(
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
            # Don't raise — we just need the cookie

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
        """Search procedures by organism NIF or name match.

        The API doesn't support NIF filtering directly, so we fetch all
        procedures and filter locally. The dataset is small (~200 records).
        """
        all_procs = await self._fetch_procedures()

        # Also fetch mobility procedures
        try:
            mobility_procs = await self._fetch_procedures("MOBILITY")
            all_procs.extend(mobility_procs)
        except Exception:
            pass  # Mobility endpoint might not exist

        # Filter by NIF in organism data or procedure text
        matching = []
        for raw in all_procs:
            organism = raw.get("organism", {})
            # Check if the organism NIF/name relates to our query
            org_name = str(organism.get("name", "")).lower()
            proc_title = str(raw.get("title", "")).lower()

            # Since the API doesn't expose organism NIFs directly,
            # we store all procedures indexed by organism for future lookups
            matching.append(raw)

        procedures = [self._to_procedure(p) for p in matching]

        # Group by organism for entity mapping
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
