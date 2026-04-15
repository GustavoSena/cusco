from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx


class DataSource(ABC):
    """Base class for all data sources."""

    name: str

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    @abstractmethod
    async def search_by_nif(self, nif: str) -> dict[str, Any]:
        """Search for entity data by NIF. Returns source-specific dict."""
        ...

    async def search_by_name(self, name: str) -> dict[str, Any]:
        """Optional: search by company name. Override if supported."""
        return {"error": f"{self.name} does not support name search"}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            headers={"User-Agent": "Cusco/0.1 (entity-intelligence)"},
        )
