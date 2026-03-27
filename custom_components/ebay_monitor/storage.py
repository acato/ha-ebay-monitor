"""Persistent storage for deduplication of seen eBay listings."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DEFAULT_MAX_SEEN_IDS, STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class SeenListingsStore:
    """Manages persistent storage of seen listings per search.

    Stores item_id -> price mappings (not just IDs) so we can detect
    price drops on previously-seen listings.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self._store = Store[dict[str, Any]](
            hass, STORAGE_VERSION + 1, STORAGE_KEY
        )
        self._data: dict[str, dict[str, float]] = {}

    async def async_load(self) -> None:
        """Load seen listings from disk."""
        stored = await self._store.async_load()
        if stored and isinstance(stored, dict):
            # Migrate from v1 (list of IDs) to v2 (dict of ID -> price)
            for search_name, value in stored.items():
                if isinstance(value, list):
                    # v1 format: list of item_id strings — migrate with price 0
                    self._data[search_name] = {iid: 0.0 for iid in value}
                elif isinstance(value, dict):
                    # v2 format: dict of item_id -> price
                    self._data[search_name] = {
                        k: float(v) for k, v in value.items()
                    }
                else:
                    self._data[search_name] = {}
        else:
            self._data = {}
        _LOGGER.debug("Loaded seen listings: %d searches tracked", len(self._data))

    async def async_save(self) -> None:
        """Persist seen listings to disk."""
        await self._store.async_save(self._data)

    def get_seen(self, search_name: str) -> dict[str, float]:
        """Return dict of previously seen item IDs -> prices for a search."""
        return dict(self._data.get(search_name, {}))

    def get_seen_ids(self, search_name: str) -> set[str]:
        """Return set of previously seen item IDs for a search."""
        return set(self._data.get(search_name, {}).keys())

    def get_price(self, search_name: str, item_id: str) -> float | None:
        """Return the last seen price for an item, or None if not seen."""
        return self._data.get(search_name, {}).get(item_id)

    def mark_seen(
        self, search_name: str, items: dict[str, float]
    ) -> None:
        """Mark items as seen with their current prices. Trims to max size."""
        existing = self._data.get(search_name, {})
        existing.update(items)
        # Keep only the most recent N items (by insertion order)
        if len(existing) > DEFAULT_MAX_SEEN_IDS:
            keys = list(existing.keys())
            trimmed = keys[-DEFAULT_MAX_SEEN_IDS:]
            existing = {k: existing[k] for k in trimmed}
        self._data[search_name] = existing

    def remove_search(self, search_name: str) -> None:
        """Remove tracking data for a deleted search."""
        self._data.pop(search_name, None)
