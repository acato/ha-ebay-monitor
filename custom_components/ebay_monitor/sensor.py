"""Sensor platform for eBay Monitor."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EbaySearchCoordinator
from .const import CONF_MAX_PRICE, CONF_SEARCH_NAME, CONF_SEARCH_QUERY, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up eBay Monitor sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators: dict[str, EbaySearchCoordinator] = data["coordinators"]

    entities = []
    for search_name, coordinator in coordinators.items():
        entities.append(EbayMonitorSensor(coordinator, entry))

    async_add_entities(entities)


class EbayMonitorSensor(CoordinatorEntity[EbaySearchCoordinator], SensorEntity):
    """Sensor showing the number of matching eBay listings for a search."""

    _attr_icon = "mdi:shopping"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "listings"

    def __init__(
        self,
        coordinator: EbaySearchCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._search_name = coordinator.search_name
        self._attr_unique_id = f"{entry.entry_id}_{self._search_name}"
        self._attr_name = f"eBay {self._search_name.replace('_', ' ').title()}"

    @property
    def native_value(self) -> int | None:
        """Return the total number of matching listings."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.total_results

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed attributes about the search results."""
        if self.coordinator.data is None:
            return {}

        result = self.coordinator.data
        config = self.coordinator.search_config

        # Find cheapest listing
        cheapest_price: float | None = None
        cheapest_title: str | None = None
        cheapest_url: str | None = None
        if result.listings:
            cheapest = min(result.listings, key=lambda x: x.price)
            cheapest_price = cheapest.price
            cheapest_title = cheapest.title
            cheapest_url = cheapest.url

        # Top 10 listings for attribute inspection
        latest = [listing.as_dict() for listing in result.listings[:10]]

        return {
            "total_results": result.total_results,
            "cheapest_price": cheapest_price,
            "cheapest_title": cheapest_title,
            "cheapest_url": cheapest_url,
            "last_updated": datetime.now().isoformat(),
            "search_query": config.get(CONF_SEARCH_QUERY, ""),
            "max_price": config.get(CONF_MAX_PRICE),
            "new_listing_count": len(self.coordinator.new_listing_ids),
            "new_listing_ids": self.coordinator.new_listing_ids,
            "price_drop_count": len(self.coordinator.price_drop_ids),
            "price_drop_ids": self.coordinator.price_drop_ids,
            "search_name": self._search_name,
            "latest_listings": latest,
        }

    @property
    def available(self) -> bool:
        """Return True if the last update was successful."""
        return self.coordinator.last_update_success
