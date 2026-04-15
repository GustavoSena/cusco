from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import fitz  # pymupdf

from ..models import DebtBracket, DebtorRecord, BRACKET_LABELS
from .base import DataSource

logger = logging.getLogger(__name__)

BASE_URL = "https://static.portaldasfinancas.gov.pt/app/devedores_static"

# C1-C6 are corporate debtor PDFs, each representing a debt bracket
PDF_FILES: dict[DebtBracket, str] = {
    DebtBracket.C1: "listaFC1.pdf",
    DebtBracket.C2: "listaFC2.pdf",
    DebtBracket.C3: "listaFC3.pdf",
    DebtBracket.C4: "listaFC4.pdf",
    DebtBracket.C5: "listaFC5.pdf",
    DebtBracket.C6: "listaFC6.pdf",
}

CACHE_DIR = Path(os.environ.get("CUSCO_CACHE_DIR", "/tmp/cusco_cache"))
CACHE_MAX_AGE_SECONDS = 7 * 24 * 3600  # 7 days (PDFs update monthly)


class DevedoresSource(DataSource):
    name = "devedores"

    def __init__(self, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async def search_by_nif(self, nif: str) -> dict[str, Any]:
        """Search all corporate debtor PDFs for the given NIF."""
        for bracket, filename in PDF_FILES.items():
            try:
                pdf_path = await self._ensure_pdf(filename)
                if pdf_path and self._nif_in_pdf(nif, pdf_path):
                    record = DebtorRecord(
                        nif=nif,
                        found=True,
                        debt_bracket=bracket,
                        debt_bracket_label=BRACKET_LABELS[bracket],
                    )
                    return {"debtor": record, "is_tax_debtor": True}
            except Exception as e:
                logger.warning(f"Error checking {filename}: {e}")
                continue

        return {
            "debtor": DebtorRecord(nif=nif, found=False),
            "is_tax_debtor": False,
        }

    async def _ensure_pdf(self, filename: str) -> Path | None:
        """Download PDF if not cached or cache is stale."""
        cached = CACHE_DIR / filename
        if cached.exists():
            age = time.time() - cached.stat().st_mtime
            if age < CACHE_MAX_AGE_SECONDS:
                return cached

        url = f"{BASE_URL}/{filename}"
        try:
            async with self._client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                cached.write_bytes(resp.content)
                logger.info(f"Downloaded {filename} ({len(resp.content)} bytes)")
                return cached
        except Exception as e:
            logger.error(f"Failed to download {filename}: {e}")
            # Return cached version even if stale
            return cached if cached.exists() else None

    def _nif_in_pdf(self, nif: str, pdf_path: Path) -> bool:
        """Search for NIF string in the PDF text."""
        try:
            doc = fitz.open(str(pdf_path))
            for page in doc:
                text = page.get_text()
                if nif in text:
                    doc.close()
                    return True
            doc.close()
            return False
        except Exception as e:
            logger.error(f"Error reading PDF {pdf_path}: {e}")
            return False
