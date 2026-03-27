"""Binary sensor platform for eBay Monitor."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EbaySearchCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up eBay Monitor binary sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators: dict[str, EbaySearchCoordinator] = data["coordinators"]

    entities = []
    for search_name, coordinator in coordinators.items():
        entities.append(EbayMonitorMatchSensor(coordinator, entry))

    async_add_entities(entities)


class EbayMonitorMatchSensor(
    CoordinatorEntity[EbaySearchCoordinator], BinarySensorEntity
):
    """Binary sensor that is ON when new unseen listings are found."""

    _attr_icon = "mdi:alert-decagram"

    def __init__(
        self,
        coordinator: EbaySearchCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)

        self._search_name = coordinator.search_name
        self._attr_unique_id = f"{entry.entry_id}_{self._search_name}_match"
        self._attr_name = f"eBay {self._search_name.replace('_', ' ').title()} Match"

    @property
    def is_on(self) -> bool | None:
        """Return True if new listings or price drops were found in the last scan."""
        if self.coordinator.data is None:
            return None
        return (
            len(self.coordinator.new_listing_ids) > 0
            or len(getattr(self.coordinator, "price_drop_ids", [])) > 0
        )

    @property
    def available(self) -> bool:
        """Return True if the last update was successful."""
        return self.coordinator.last_update_success
