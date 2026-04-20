from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable

import httpx


class DataSource(ABC):
    """Base class for all data sources."""

    name: str

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        # Per-instance lock for `_ensure_loaded`-style one-time loading.
        # Subclasses that override `_ensure_loaded` should wrap the body in
        # `await self._load_once(self._do_load)` (see `_load_once` below).
        self._load_lock: asyncio.Lock | None = None

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

    async def _load_once(
        self,
        loader: Callable[[], Awaitable[None]],
        is_loaded: Callable[[], bool],
    ) -> None:
        """Serialize concurrent calls to a one-time loader.

        Without a lock, two concurrent first-time queries (e.g. background
        warmup + a user-triggered search) both see `is_loaded() == False`,
        both enter `loader()`, and both re-parse/re-index the same XLSX
        download — wasting CPU and memory. This helper double-checks the
        flag inside the lock so only one coroutine does the work.

        Usage from a subclass:
            async def _ensure_loaded(self) -> None:
                await self._load_once(
                    loader=self._do_load,
                    is_loaded=lambda: self._loaded,
                )
        """
        if is_loaded():
            return
        if self._load_lock is None:
            self._load_lock = asyncio.Lock()
        async with self._load_lock:
            if is_loaded():
                return
            await loader()
