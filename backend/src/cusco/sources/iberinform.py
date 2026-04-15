from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx

from .base import DataSource

logger = logging.getLogger(__name__)

JINA_SEARCH_URL = "https://s.jina.ai/"
JINA_READER_URL = "https://r.jina.ai/"


class IberinformSource(DataSource):
    name = "iberinform"

    async def _find_iberinform_url(self, nif: str, api_key: str) -> str | None:
        """Search Jina for the iberinform page matching this NIF."""
        logger.info(f"[iberinform] Searching Jina for NIF {nif} on iberinform.pt")
        async with self._client() as client:
            resp = await client.post(
                JINA_SEARCH_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-Site": "iberinform.pt",
                },
                json={"q": nif, "num": "3"},
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract URLs from search results
            results = data.get("data", [])
            logger.info(f"[iberinform] Search returned {len(results)} results:")
            for i, r in enumerate(results):
                logger.info(f"[iberinform]   {i+1}. {r.get('title', '?')} — {r.get('url', '?')}")
            for result in results:
                url = result.get("url", "")
                if "iberinform.pt" in url and re.search(r"/empresa/", url):
                    return url

            # Fallback: check if any result mentions iberinform
            for result in results:
                url = result.get("url", "")
                if "iberinform.pt" in url:
                    return url

        return None

    async def _scrape_url(self, target_url: str, api_key: str) -> str | None:
        """Scrape a URL using Jina Reader."""
        url = f"{JINA_READER_URL}{target_url}"

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            resp = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                    "X-Retain-Images": "none",
                    "X-Return-Format": "markdown",
                },
            )
            resp.raise_for_status()

            data = resp.json()
            content = data.get("data", {}).get("content", "").strip()
            if content:
                logger.info(f"[iberinform] Scraped {len(content)} chars (raw)")
                content = self._extract_sections(content)
                if content:
                    logger.info(f"[iberinform] Extracted {len(content)} chars. Preview: {content[:200]}")
                else:
                    logger.info("[iberinform] No relevant sections found in scraped content")
            else:
                logger.info("[iberinform] Scrape returned empty content")
            return content if content else None

    @staticmethod
    def _extract_sections(markdown: str) -> str | None:
        """Extract only 'Dados Gerais' and 'Resumo' sections from the page."""
        sections: list[str] = []

        # Split by markdown headings
        parts = re.split(r"(^#{1,4}\s+.+$)", markdown, flags=re.MULTILINE)

        capture = False
        for part in parts:
            # Check if this is a heading we want
            if re.match(r"^#{1,4}\s+", part):
                heading_text = re.sub(r"^#{1,4}\s+", "", part).strip().lower()
                capture = "dados gerais" in heading_text or "resumo" in heading_text
                if capture:
                    sections.append(part)
            elif capture:
                sections.append(part)

        result = "\n".join(sections).strip()
        return result if result else None

    async def search_by_nif(self, nif: str) -> dict[str, Any]:
        api_key = os.environ.get("JINA_API_KEY", "")
        if not api_key:
            logger.warning("[iberinform] JINA_API_KEY not set, skipping")
            return {"iberinform_content": None}

        # Step 1: find the correct iberinform URL via search
        target_url = await self._find_iberinform_url(nif, api_key)
        if not target_url:
            logger.info(f"No iberinform page found for NIF {nif}")
            return {"iberinform_content": None}

        logger.info(f"Found iberinform URL for NIF {nif}: {target_url}")

        # Step 2: scrape the page content
        try:
            content = await self._scrape_url(target_url, api_key)
        except Exception as e:
            logger.error(f"[iberinform] Scrape failed for {target_url}: {type(e).__name__}: {e}", exc_info=True)
            return {"iberinform_content": None}
        return {"iberinform_content": content}
