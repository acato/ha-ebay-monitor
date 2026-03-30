"""eBay Monitor - Monitor eBay searches and notify on new listings / price drops."""

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
    CONF_BUYING_OPTIONS,
    CONF_CATEGORY_ID,
    CONF_CERT_ID,
    CONF_CONDITION,
    CONF_LOCATION_COUNTRY,
    CONF_MAX_PRICE,
    CONF_MIN_PRICE,
    CONF_NOTIFY_SERVICES,
    CONF_SCAN_INTERVAL,
    CONF_SEARCH_NAME,
    CONF_SEARCH_QUERY,
    CONF_SEARCHES,
    CONF_SITE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SITE,
    DOMAIN,
    EVENT_NEW_LISTING,
    EVENT_PRICE_DROP,
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

    store = SeenListingsStore(hass)
    await store.async_load()

    searches = entry.options.get(CONF_SEARCHES, [])
    notify_services = entry.options.get(CONF_NOTIFY_SERVICES, [])

    coordinators: dict[str, EbaySearchCoordinator] = {}

    for search_config in searches:
        search_name = search_config[CONF_SEARCH_NAME]
        interval = search_config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        coordinator = EbaySearchCoordinator(
            hass=hass,
            client=client,
            store=store,
            search_config=search_config,
            notify_services=notify_services,
            update_interval=timedelta(minutes=interval),
        )

        coordinators[search_name] = coordinator

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "store": store,
        "coordinators": coordinators,
    }

    # Initial refresh for all coordinators
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload on options change (search added/removed, notify service changed)
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
    """Handle options update - reload the entry to pick up changes."""
    await hass.config_entries.async_reload(entry.entry_id)


class EbaySearchCoordinator(DataUpdateCoordinator[EbaySearchResult]):
    """Coordinator that polls eBay for a single search configuration."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: EbayApiClient,
        store: SeenListingsStore,
        search_config: dict[str, Any],
        notify_services: list[str],
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        self._client = client
        self._store = store
        self.search_config = search_config
        self.search_name: str = search_config[CONF_SEARCH_NAME]
        self._notify_services = notify_services
        self.new_listing_ids: list[str] = []
        self.price_drop_ids: list[str] = []

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

        # Classify listings: new vs price-dropped vs unchanged
        seen = self._store.get_seen(self.search_name)
        new_listings = []
        price_drops = []

        for listing in result.listings:
            prev_price = seen.get(listing.item_id)
            if prev_price is None:
                new_listings.append(listing)
            elif prev_price > 0 and listing.price < prev_price:
                price_drops.append((listing, prev_price))

        self.new_listing_ids = [item.item_id for item in new_listings]
        self.price_drop_ids = [item.item_id for item, _ in price_drops]

        # Fire HA events and send notifications for new listings
        for listing in new_listings:
            event_data = {
                "search_name": self.search_name,
                **listing.as_dict(),
            }
            self.hass.bus.async_fire(EVENT_NEW_LISTING, event_data)

            _LOGGER.info(
                "New eBay listing [%s]: %s - $%.2f (%s)",
                self.search_name,
                listing.title,
                listing.price,
                listing.item_id,
            )

            await self._send_notification(
                alert_type="New Listing",
                listing=listing,
            )

        # Fire HA events and send notifications for price drops
        for listing, old_price in price_drops:
            drop_amount = old_price - listing.price
            drop_pct = (drop_amount / old_price) * 100

            event_data = {
                "search_name": self.search_name,
                "previous_price": old_price,
                "drop_amount": round(drop_amount, 2),
                "drop_percentage": round(drop_pct, 1),
                **listing.as_dict(),
            }
            self.hass.bus.async_fire(EVENT_PRICE_DROP, event_data)

            _LOGGER.info(
                "Price drop [%s]: %s - $%.2f -> $%.2f (-%s%%) (%s)",
                self.search_name,
                listing.title,
                old_price,
                listing.price,
                f"{drop_pct:.1f}",
                listing.item_id,
            )

            await self._send_notification(
                alert_type="Price Drop",
                listing=listing,
                old_price=old_price,
                drop_amount=drop_amount,
                drop_pct=drop_pct,
            )

        # Update seen store with current prices
        if result.listings:
            items = {item.item_id: item.price for item in result.listings}
            self._store.mark_seen(self.search_name, items)
            await self._store.async_save()

        return result

    async def _send_notification(
        self,
        alert_type: str,
        listing: Any,
        old_price: float | None = None,
        drop_amount: float | None = None,
        drop_pct: float | None = None,
    ) -> None:
        """Send notification via configured notify services."""
        if not self._notify_services:
            return

        query = self.search_config.get(CONF_SEARCH_QUERY, self.search_name)
        title = f"eBay: {query} - {alert_type}"

        if alert_type == "Price Drop" and old_price is not None:
            body = (
                f"{listing.title}\n"
                f"Price: ${listing.price:.2f} (was ${old_price:.2f}, "
                f"-${drop_amount:.2f} / -{drop_pct:.1f}%)\n"
                f"Seller: {listing.seller_name}\n"
                f"{listing.url}"
            )
        else:
            body = (
                f"{listing.title}\n"
                f"Price: ${listing.price:.2f}\n"
                f"Seller: {listing.seller_name}\n"
                f"{listing.url}"
            )

        # Build notification data with actionable buttons for mobile
        notify_data: dict[str, Any] = {
            "url": listing.url,
            "clickAction": listing.url,
        }

        # Add actionable notification actions for mobile app
        actions = [
            {
                "action": "URI",
                "title": "View on eBay",
                "uri": listing.url,
            },
        ]
        if listing.is_fixed_price:
            actions.append(
                {
                    "action": "URI",
                    "title": "Buy Now",
                    "uri": listing.url,
                }
            )

        notify_data["actions"] = actions

        # Add image if available
        if listing.image_url:
            notify_data["image"] = listing.image_url

        for service_name in self._notify_services:
            # service_name is like "mobile_app_iphone" or "telegram"
            # The notify domain uses notify.{service_name}
            try:
                await self.hass.services.async_call(
                    "notify",
                    service_name,
                    {
                        "title": title,
                        "message": body,
                        "data": notify_data,
                    },
                    blocking=False,
                )
            except Exception:
                _LOGGER.exception(
                    "Failed to send eBay notification via notify.%s",
                    service_name,
                )
