"""Sensor platform for eBay Monitor."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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
    """Sensor showing eBay search results."""

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
        """Return the number of new (unseen) listings from last scan."""
        if self.coordinator.data is None:
            return None
        return len(self.coordinator.new_listing_ids)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed attributes about the search results."""
        if self.coordinator.data is None:
            return {}

        result = self.coordinator.data
        config = self.coordinator.search_config

        # Include up to 10 latest listings as attributes
        latest = [listing.as_dict() for listing in result.listings[:10]]

        return {
            "total_results": result.total_results,
            "latest_listings": latest,
            "search_query": config.get(CONF_SEARCH_QUERY, ""),
            "max_price": config.get(CONF_MAX_PRICE),
            "new_listing_ids": self.coordinator.new_listing_ids,
            "search_name": self._search_name,
        }

    @property
    def available(self) -> bool:
        """Return True if the last update was successful."""
        return self.coordinator.last_update_success
