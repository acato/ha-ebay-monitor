"""Config flow for eBay Monitor integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BUYING_OPTIONS,
    CONDITIONS,
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
    EBAY_SITES,
)
from .ebay_api import EbayApiClient

_LOGGER = logging.getLogger(__name__)


class EbayMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for eBay Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: API credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = EbayApiClient(
                app_id=user_input[CONF_APP_ID],
                cert_id=user_input[CONF_CERT_ID],
                site=user_input.get(CONF_SITE, DEFAULT_SITE),
                session=session,
            )

            if await client.validate_credentials():
                await self.async_set_unique_id(user_input[CONF_APP_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="eBay Monitor",
                    data={
                        CONF_APP_ID: user_input[CONF_APP_ID],
                        CONF_CERT_ID: user_input[CONF_CERT_ID],
                        CONF_SITE: user_input.get(CONF_SITE, DEFAULT_SITE),
                    },
                    options={
                        CONF_SEARCHES: [],
                        CONF_NOTIFY_SERVICES: [],
                    },
                )
            else:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_APP_ID): str,
                    vol.Required(CONF_CERT_ID): str,
                    vol.Optional(CONF_SITE, default=DEFAULT_SITE): vol.In(
                        EBAY_SITES
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "developer_url": "https://developer.ebay.com/my/keys"
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return EbayMonitorOptionsFlow(config_entry)


class EbayMonitorOptionsFlow(OptionsFlow):
    """Handle options flow for eBay Monitor (manage searches + notifications)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._searches: list[dict[str, Any]] = list(
            config_entry.options.get(CONF_SEARCHES, [])
        )
        self._notify_services: list[str] = list(
            config_entry.options.get(CONF_NOTIFY_SERVICES, [])
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage searches: show menu."""
        search_names = [s[CONF_SEARCH_NAME] for s in self._searches]

        menu_options = ["add_search", "configure_notifications"]
        if search_names:
            menu_options.insert(1, "remove_search")

        return self.async_show_menu(
            step_id="init",
            menu_options=menu_options,
            description_placeholders={
                "searches": (
                    f"Current searches: {', '.join(search_names)}"
                    if search_names
                    else "No searches configured yet."
                ),
                "notify_services": (
                    f"Notify via: {', '.join(self._notify_services)}"
                    if self._notify_services
                    else "No notification services configured."
                ),
            },
        )

    async def async_step_add_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new search."""
        errors: dict[str, str] = {}

        if user_input is not None:
            existing_names = {s[CONF_SEARCH_NAME] for s in self._searches}
            search_name = user_input[CONF_SEARCH_NAME].lower().replace(" ", "_")
            user_input[CONF_SEARCH_NAME] = search_name

            if search_name in existing_names:
                errors[CONF_SEARCH_NAME] = "name_exists"
            else:
                search = {
                    k: v for k, v in user_input.items() if v is not None and v != ""
                }
                search[CONF_SEARCH_NAME] = search_name
                search[CONF_SEARCH_QUERY] = user_input[CONF_SEARCH_QUERY]

                self._searches.append(search)
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SEARCHES: self._searches,
                        CONF_NOTIFY_SERVICES: self._notify_services,
                    },
                )

        return self.async_show_form(
            step_id="add_search",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SEARCH_NAME): str,
                    vol.Required(CONF_SEARCH_QUERY): str,
                    vol.Optional(CONF_MAX_PRICE): vol.Coerce(float),
                    vol.Optional(CONF_MIN_PRICE): vol.Coerce(float),
                    vol.Optional(CONF_CONDITION): vol.All(
                        vol.Ensure(list), [vol.In(CONDITIONS)]
                    ),
                    vol.Optional(CONF_LOCATION_COUNTRY): str,
                    vol.Optional(CONF_BUYING_OPTIONS): vol.All(
                        vol.Ensure(list), [vol.In(BUYING_OPTIONS)]
                    ),
                    vol.Optional(CONF_CATEGORY_ID): str,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=1440)),
                }
            ),
            errors=errors,
        )

    async def async_step_remove_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove an existing search."""
        if user_input is not None:
            name_to_remove = user_input["search_to_remove"]
            self._searches = [
                s for s in self._searches if s[CONF_SEARCH_NAME] != name_to_remove
            ]
            return self.async_create_entry(
                title="",
                data={
                    CONF_SEARCHES: self._searches,
                    CONF_NOTIFY_SERVICES: self._notify_services,
                },
            )

        search_names = {
            s[CONF_SEARCH_NAME]: s[CONF_SEARCH_NAME] for s in self._searches
        }

        return self.async_show_form(
            step_id="remove_search",
            data_schema=vol.Schema(
                {
                    vol.Required("search_to_remove"): vol.In(search_names),
                }
            ),
        )

    async def async_step_configure_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure notification services."""
        if user_input is not None:
            raw = user_input.get(CONF_NOTIFY_SERVICES, "")
            if raw.strip():
                self._notify_services = [
                    s.strip() for s in raw.split(",") if s.strip()
                ]
            else:
                self._notify_services = []

            return self.async_create_entry(
                title="",
                data={
                    CONF_SEARCHES: self._searches,
                    CONF_NOTIFY_SERVICES: self._notify_services,
                },
            )

        current = ", ".join(self._notify_services)

        return self.async_show_form(
            step_id="configure_notifications",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NOTIFY_SERVICES,
                        default=current,
                    ): str,
                }
            ),
            description_placeholders={
                "example": "mobile_app_iphone, telegram, persistent_notification"
            },
        )
