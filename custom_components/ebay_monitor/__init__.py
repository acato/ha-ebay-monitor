"""eBay Monitor - Monitor eBay searches and notify on new listings."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_APP_ID,
    CONF_CERT_ID,
    CONF_BUYING_OPTIONS,
    CONF_CATEGORY_ID,
    CONF_CONDITION,
    CONF_LOCATION_COUNTRY,
    CONF_MAX_PRICE,
    CONF_MIN_PRICE,
    CONF_SCAN_INTERVAL,
    CONF_SEARCH_NAME,
    CONF_SEARCH_QUERY,
    CONF_SEARCHES,
    CONF_SITE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SITE,
    DOMAIN,
    EVENT_NEW_LISTING,
    PLATFORMS,
)
from .ebay_api import EbayApiClient, EbaySearchResult
from .storage import SeenListingsStore

_LOGGER = logging.getLogger(__name__)

type EbayMonitorConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: EbayMonitorConfigEntry) -> bool:
    """Set up eBay Monitor from a config entry."""
    session = async_get_clientsession(hass)

    client = EbayApiClient(
        app_id=entry.data[CONF_APP_ID],
        cert_id=entry.data[CONF_CERT_ID],
        site=entry.data.get(CONF_SITE, DEFAULT_SITE),
        session=session,
    )

    # Initialize seen listings store
    store = SeenListingsStore(hass)
    await store.async_load()

    searches = entry.options.get(CONF_SEARCHES, [])

    # Create a coordinator for each search
    coordinators: dict[str, EbaySearchCoordinator] = {}

    for search_config in searches:
        search_name = search_config[CONF_SEARCH_NAME]
        interval = search_config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        coordinator = EbaySearchCoordinator(
            hass=hass,
            client=client,
            store=store,
            search_config=search_config,
            update_interval=timedelta(minutes=interval),
        )

        coordinators[search_name] = coordinator

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "store": store,
        "coordinators": coordinators,
    }

    # Do initial refresh for all coordinators
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options updates (search added/removed/changed)
    entry.async_on_unload(entry.add_update_listener(async_options_updated))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EbayMonitorConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_options_updated(
    hass: HomeAssistant, entry: EbayMonitorConfigEntry
) -> None:
    """Handle options update - reload the entry to pick up search changes."""
    await hass.config_entries.async_reload(entry.entry_id)


class EbaySearchCoordinator(DataUpdateCoordinator[EbaySearchResult]):
    """Coordinator that polls eBay for a single search configuration."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: EbayApiClient,
        store: SeenListingsStore,
        search_config: dict[str, Any],
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        self._client = client
        self._store = store
        self.search_config = search_config
        self.search_name: str = search_config[CONF_SEARCH_NAME]
        self.new_listing_ids: list[str] = []

        super().__init__(
            hass,
            _LOGGER,
            name=f"eBay Monitor - {self.search_name}",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> EbaySearchResult:
        """Fetch data from eBay Browse API."""
        config = self.search_config

        try:
            result = await self._client.search(
                query=config[CONF_SEARCH_QUERY],
                max_price=config.get(CONF_MAX_PRICE),
                min_price=config.get(CONF_MIN_PRICE),
                conditions=config.get(CONF_CONDITION),
                location_country=config.get(CONF_LOCATION_COUNTRY),
                buying_options=config.get(CONF_BUYING_OPTIONS),
                category_id=config.get(CONF_CATEGORY_ID),
            )
        except Exception as err:
            raise UpdateFailed(f"Error fetching eBay data: {err}") from err

        if result.error:
            raise UpdateFailed(f"eBay API error: {result.error}")

        # Deduplication: find new listings
        seen_ids = self._store.get_seen_ids(self.search_name)
        new_listings = [
            listing for listing in result.listings
            if listing.item_id not in seen_ids
        ]

        self.new_listing_ids = [l.item_id for l in new_listings]

        # Fire events for each new listing
        for listing in new_listings:
            self.hass.bus.async_fire(
                EVENT_NEW_LISTING,
                {
                    "search_name": self.search_name,
                    **listing.as_dict(),
                },
            )
            _LOGGER.info(
                "New eBay listing found [%s]: %s - $%.2f (%s)",
                self.search_name,
                listing.title,
                listing.price,
                listing.item_id,
            )

        # Mark all current results as seen
        if result.listings:
            all_ids = [l.item_id for l in result.listings]
            self._store.mark_seen(self.search_name, all_ids)
            await self._store.async_save()

        return result
