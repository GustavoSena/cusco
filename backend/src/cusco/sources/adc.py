"""Autoridade da Concorrência (AdC) — Portuguese Competition Authority.

Scrapes the PesquisAdC case database to extract:
- Práticas anticoncorrenciais (anti-competitive practices): cartels, abuse of dominance
- Contencioso (judicial decisions): court challenges to AdC decisions
- Concentrações (merger control): notified mergers/acquisitions
- Estudos/Pareceres/Recomendações (studies, opinions, recommendations)

The database is at https://extranet.concorrencia.pt/PesquisAdC/SearchNew.aspx
and uses OutSystems which requires a headless browser to render results.

Data is scraped and cached locally, then indexed by entity name for search.

Note: intentionally NOT migrated to SQLite (unlike `contracts`/`entities`/
`prr`). The AdC dataset is ~400 processes — negligible memory, and the
scraping pipeline's once-a-week refresh makes the JSON file cache
perfectly adequate.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from ..models import AdCProcess
from .base import DataSource

logger = logging.getLogger(__name__)

ADC_SEARCH_URL = (
    "https://extranet.concorrencia.pt/PesquisAdC/SearchNew.aspx?IsEnglish=False"
)
ADC_DETAIL_BASE = "https://extranet.concorrencia.pt/PesquisAdC/Page.aspx"

CACHE_DIR = Path(os.environ.get("CUSCO_CACHE_DIR", "/tmp/cusco_cache"))
CACHE_MAX_AGE_SECONDS = 7 * 24 * 3600  # 1 week (data changes slowly)

# Table type mapping (order matches the page layout)
TABLE_TYPES = [
    "praticas_anticoncorrenciais",
    "concentracoes",
    "estudos_pareceres",
    "contencioso",
]


class AdCSource(DataSource):
    """Autoridade da Concorrência case database."""

    name = "adc"

    def __init__(self, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self._processes: list[dict] = []
        self._by_entity: dict[str, list[dict]] = {}  # lowercase entity -> processes
        self._loaded = False
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async def _ensure_loaded(self) -> None:
        """Idempotent load — serialized via `_load_once` so concurrent
        first queries don't each re-download + re-parse the dataset."""
        await self._load_once(self._do_load, lambda: self._loaded)

    async def _do_load(self) -> None:
        cache_file = CACHE_DIR / "adc_processes.json"

        # Check cache
        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < CACHE_MAX_AGE_SECONDS:
                logger.info("Loading AdC processes from cache")
                with open(cache_file) as f:
                    data = json.load(f)
                self._index_processes(data)
                self._loaded = True
                return

        # Scrape fresh data
        try:
            data = await self._scrape_all()
            with open(cache_file, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._index_processes(data)
        except Exception as e:
            logger.warning(f"Failed to scrape AdC: {e}")
            # Try stale cache
            if cache_file.exists():
                logger.info("Falling back to stale AdC cache")
                with open(cache_file) as f:
                    data = json.load(f)
                self._index_processes(data)

        self._loaded = True

    async def _scrape_all(self) -> dict[str, list[dict]]:
        """Scrape all process tables from the AdC search page using playwright."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(
                "playwright is required for AdC scraping. "
                "Install with: pip install playwright && python -m playwright install chromium"
            )
            return {}

        all_data: dict[str, list[dict]] = {}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            logger.info("Scraping AdC search page...")
            await page.goto(ADC_SEARCH_URL, wait_until="networkidle")
            await page.wait_for_timeout(3000)

            # Set all page-size dropdowns to 100
            selects = await page.evaluate(
                """() => Array.from(
                    document.querySelectorAll('select[id*="PageNumberDropDown"]')
                ).map(s => s.id)"""
            )
            for sid in selects:
                try:
                    await page.select_option(f"#{sid}", value="__ossli_100")
                except Exception:
                    pass
            await page.wait_for_timeout(5000)

            # Extract tables
            tables = await page.evaluate(
                """() => {
                const tables = document.querySelectorAll('table');
                return Array.from(tables)
                    .filter(t => t.querySelectorAll('th').length > 1)
                    .map(table => {
                        const headers = Array.from(table.querySelectorAll('th'))
                            .map(th => th.innerText.trim());
                        const rows = [];
                        table.querySelectorAll('tbody tr, tr').forEach(tr => {
                            if (tr.querySelector('th')) return;
                            const cells = Array.from(tr.querySelectorAll('td')).map(td => ({
                                text: td.innerText.trim(),
                                links: Array.from(td.querySelectorAll('a')).map(a => ({
                                    text: a.innerText.trim(),
                                    href: a.href
                                }))
                            }));
                            if (cells.length > 1) rows.push(cells);
                        });
                        return {headers, rows};
                    });
            }"""
            )

            for i, table in enumerate(tables):
                table_type = TABLE_TYPES[i] if i < len(TABLE_TYPES) else f"table_{i}"
                processes = []
                for row in table["rows"]:
                    proc: dict[str, Any] = {"type": table_type}
                    for j, header in enumerate(table["headers"]):
                        if j < len(row):
                            proc[header] = row[j]["text"]
                            for link in row[j].get("links", []):
                                href = link.get("href", "")
                                if not href or href == "#":
                                    continue
                                if "pdf" in link.get("text", "").lower():
                                    proc["pdf_url"] = href
                                elif "Page.aspx" in href:
                                    proc["detail_url"] = href
                    processes.append(proc)
                all_data[table_type] = processes
                logger.info(f"AdC {table_type}: {len(processes)} processes")

            await browser.close()

        return all_data

    def _index_processes(self, data: dict[str, list[dict]]) -> None:
        """Build entity name index for fast lookups."""
        self._processes = []
        self._by_entity = {}

        for table_type, processes in data.items():
            for proc in processes:
                # Ensure type is set (may already be set from scrape)
                if "type" not in proc:
                    proc = {**proc, "type": table_type}
                self._processes.append(proc)

                # Extract and index entity names
                entities_text = proc.get("Entidades", "")
                if not entities_text or entities_text == "*":
                    continue

                for entity_name in self._parse_entities(entities_text):
                    key = entity_name.lower().strip()
                    if key and len(key) > 2:
                        self._by_entity.setdefault(key, []).append(proc)

        logger.info(
            f"Indexed AdC: {len(self._processes)} processes, "
            f"{len(self._by_entity)} unique entity names"
        )

    def _parse_entities(self, text: str) -> list[str]:
        """Parse entity names from AdC entity field.

        The field may contain multiple entities separated by newlines,
        with "Ver mais." links inline.
        """
        names = []
        for line in text.replace("\n", ",").split(","):
            name = line.strip()
            name = re.sub(r"\s*Ver mais\.?\s*", "", name)
            name = re.sub(r"\s*-\s*Adquirent[ea]?\s*$", "", name)
            name = re.sub(r"\s*-\s*Adquirid[ao]?\s*$", "", name)
            name = name.strip(" -")
            if name and len(name) > 2 and name != "*":
                names.append(name)
        return names

    def _to_process(self, raw: dict) -> AdCProcess:
        """Convert raw dict to AdCProcess model."""
        entities_text = raw.get("Entidades", "")
        entities = self._parse_entities(entities_text) if entities_text else []

        return AdCProcess(
            process_number=raw.get("N.º de processo", ""),
            process_type=raw.get("type", ""),
            entities=entities,
            sector=raw.get("Setor", ""),
            practice_type=raw.get("Prática investigada", ""),
            year_opened=raw.get("Ano de abertura", raw.get("Ano de notificação", "")),
            year_decided=raw.get(
                "Ano de decisão", raw.get("Ano da decisão judicial", "")
            ),
            final_decision=raw.get("Decisão final", ""),
            status=raw.get("Estado do processo", ""),
            title=raw.get("Título", ""),
            court=raw.get("Tribunal", ""),
            court_process_number=raw.get("Nº. do processo em tribunal", ""),
            origin_process=raw.get("Processo de origem", ""),
            detail_url=raw.get("detail_url", ""),
            pdf_url=raw.get("pdf_url", ""),
        )

    async def search_by_nif(self, nif: str) -> dict[str, Any]:
        """Search AdC processes.

        The AdC database doesn't contain NIFs directly — it uses company names.
        This method returns all processes (to be filtered by entity name matching
        at a higher level, e.g. by cross-referencing with IMPIC entity names).
        """
        await self._ensure_loaded()

        # We can't search by NIF directly, but we can return the full dataset
        # for the main.py to cross-reference with entity names from other sources
        return {
            "adc_processes": [],  # Empty by default — enriched in main.py
            "adc_total_available": len(self._processes),
        }

    async def search_by_entity_name(self, name: str) -> list[AdCProcess]:
        """Search AdC processes by entity name (substring match)."""
        await self._ensure_loaded()

        query = name.lower().strip()
        if not query or len(query) < 2:
            return []

        matching: list[AdCProcess] = []
        seen_numbers: set[str] = set()

        # Exact match first
        if query in self._by_entity:
            for proc in self._by_entity[query]:
                num = proc.get("N.º de processo", "")
                if num not in seen_numbers:
                    seen_numbers.add(num)
                    matching.append(self._to_process(proc))

        # Substring match
        for entity_key, procs in self._by_entity.items():
            if query in entity_key and entity_key != query:
                for proc in procs:
                    num = proc.get("N.º de processo", "")
                    if num not in seen_numbers:
                        seen_numbers.add(num)
                        matching.append(self._to_process(proc))
            if len(matching) >= 50:
                break

        return matching

    async def search_by_name(self, name: str) -> dict[str, Any]:
        """Search by company name."""
        processes = await self.search_by_entity_name(name)
        return {
            "adc_processes": processes,
            "has_competition_issues": any(
                p.process_type == "praticas_anticoncorrenciais" for p in processes
            ),
        }
