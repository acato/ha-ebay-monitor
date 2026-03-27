"""Persistent storage for deduplication of seen eBay listings."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DEFAULT_MAX_SEEN_IDS, STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class SeenListingsStore:
    """Manages persistent storage of seen listing IDs per search."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, list[str]] = {}

    async def async_load(self) -> None:
        """Load seen listings from disk."""
        stored = await self._store.async_load()
        if stored and isinstance(stored, dict):
            self._data = stored
        else:
            self._data = {}
        _LOGGER.debug("Loaded seen listings: %d searches tracked", len(self._data))

    async def async_save(self) -> None:
        """Persist seen listings to disk."""
        await self._store.async_save(self._data)

    def get_seen_ids(self, search_name: str) -> set[str]:
        """Return set of previously seen item IDs for a search."""
        return set(self._data.get(search_name, []))

    def mark_seen(self, search_name: str, item_ids: list[str]) -> None:
        """Mark item IDs as seen for a search. Trims to max size."""
        existing = self._data.get(search_name, [])
        combined = existing + [iid for iid in item_ids if iid not in existing]
        # Keep only the most recent N IDs
        self._data[search_name] = combined[-DEFAULT_MAX_SEEN_IDS:]

    def remove_search(self, search_name: str) -> None:
        """Remove tracking data for a deleted search."""
        self._data.pop(search_name, None)
