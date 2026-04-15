from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from ..models import InsolvencyProceeding
from .base import DataSource

logger = logging.getLogger(__name__)

CITIUS_URL = "https://www.citius.mj.pt/portal/consultas/ConsultasCire.aspx"


class CitiusSource(DataSource):
    name = "citius"

    async def search_by_nif(self, nif: str) -> dict[str, Any]:
        async with self._client() as client:
            # Step 1: GET the page to extract ASP.NET form tokens
            page = await client.get(CITIUS_URL)
            page.raise_for_status()

            soup = BeautifulSoup(page.text, "html.parser")
            form_data = self._extract_form_tokens(soup)

            # Step 2: Fill in the NIF search field and POST
            form_data.update(
                {
                    "ctl00$MainContent$ddlTipoEntidade": "NIF/NIPC",
                    "ctl00$MainContent$txtEntidade": nif,
                    "ctl00$MainContent$btnPesquisar": "Pesquisar",
                    # Leave other fields empty/default
                    "ctl00$MainContent$txtProcesso": "",
                    "ctl00$MainContent$txtDataDe": "",
                    "ctl00$MainContent$txtDataAte": "",
                    "ctl00$MainContent$ddlComarca": "",
                    "ctl00$MainContent$ddlGrupoAcao": "",
                    "ctl00$MainContent$ddlAcao": "",
                }
            )

            resp = await client.post(CITIUS_URL, data=form_data)
            resp.raise_for_status()

            # Step 3: Parse results
            results_soup = BeautifulSoup(resp.text, "html.parser")
            proceedings = self._parse_results(results_soup)

            return {
                "insolvency_proceedings": proceedings,
                "has_insolvency": len(proceedings) > 0,
            }

    def _extract_form_tokens(self, soup: BeautifulSoup) -> dict[str, str]:
        """Extract __VIEWSTATE and other ASP.NET hidden fields."""
        tokens = {}
        for field_name in [
            "__VIEWSTATE",
            "__VIEWSTATEGENERATOR",
            "__EVENTVALIDATION",
            "__EVENTTARGET",
            "__EVENTARGUMENT",
        ]:
            field = soup.find("input", {"name": field_name})
            if field:
                tokens[field_name] = field.get("value", "")
        return tokens

    def _parse_results(self, soup: BeautifulSoup) -> list[InsolvencyProceeding]:
        """Parse the results table from CITIUS response."""
        proceedings: list[InsolvencyProceeding] = []

        # Look for the results grid/table
        table = soup.find("table", {"id": re.compile(r"grdLista|GridView", re.I)})
        if not table:
            # Try any table with data rows
            tables = soup.find_all("table", class_=re.compile(r"grid|result", re.I))
            table = tables[0] if tables else None

        if not table:
            # Check for "no results" message
            no_results = soup.find(
                string=re.compile(r"sem resultado|nenhum registo", re.I)
            )
            if no_results:
                logger.info("CITIUS: no insolvency results found")
            return proceedings

        rows = table.find_all("tr")
        for row in rows[1:]:  # Skip header row
            cells = row.find_all("td")
            if len(cells) >= 3:
                proceeding = InsolvencyProceeding(
                    court=cells[0].get_text(strip=True) if len(cells) > 0 else "",
                    process_number=(
                        cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    ),
                    date=cells[2].get_text(strip=True) if len(cells) > 2 else "",
                    description=(
                        cells[3].get_text(strip=True) if len(cells) > 3 else ""
                    ),
                    action_type=(
                        cells[4].get_text(strip=True) if len(cells) > 4 else ""
                    ),
                )
                proceedings.append(proceeding)

        return proceedings
