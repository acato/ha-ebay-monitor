"""eBay Browse API client for the eBay Monitor integration."""

from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import (
    EBAY_AUTH_SCOPE,
    EBAY_AUTH_URL,
    EBAY_SEARCH_URL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class EbayListing:
    """Represents a single eBay listing."""

    item_id: str
    title: str
    price: float
    currency: str
    condition: str
    url: str
    image_url: str | None
    seller_name: str
    seller_feedback_percentage: str
    seller_feedback_score: int
    buying_options: list[str]
    bid_count: int
    time_remaining: str | None
    item_location: str
    category: str

    def as_dict(self) -> dict[str, Any]:
        """Return listing as a dictionary for sensor attributes."""
        return {
            "item_id": self.item_id,
            "title": self.title,
            "price": self.price,
            "currency": self.currency,
            "condition": self.condition,
            "url": self.url,
            "image_url": self.image_url,
            "seller_name": self.seller_name,
            "seller_feedback_percentage": self.seller_feedback_percentage,
            "seller_feedback_score": self.seller_feedback_score,
            "buying_options": self.buying_options,
            "bid_count": self.bid_count,
            "time_remaining": self.time_remaining,
            "item_location": self.item_location,
            "category": self.category,
        }


@dataclass
class EbaySearchResult:
    """Result of an eBay search."""

    total_results: int
    listings: list[EbayListing] = field(default_factory=list)
    error: str | None = None


class EbayApiClient:
    """Client for the eBay Browse API."""

    def __init__(
        self,
        app_id: str,
        cert_id: str,
        site: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client."""
        self._app_id = app_id
        self._cert_id = cert_id
        self._site = site
        self._session = session
        self._access_token: str | None = None
        self._token_expiry: float = 0

    async def _ensure_token(self) -> None:
        """Obtain or refresh the application access token."""
        if self._access_token and time.time() < self._token_expiry - 300:
            return  # Token still valid (with 5-minute buffer)

        credentials = base64.b64encode(
            f"{self._app_id}:{self._cert_id}".encode()
        ).decode()

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {credentials}",
        }

        data = {
            "grant_type": "client_credentials",
            "scope": EBAY_AUTH_SCOPE,
        }

        try:
            async with self._session.post(
                EBAY_AUTH_URL, headers=headers, data=data
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    _LOGGER.error(
                        "eBay token request failed (%s): %s",
                        resp.status,
                        error_text,
                    )
                    raise EbayApiError(
                        f"Token request failed with status {resp.status}"
                    )

                result = await resp.json()
                self._access_token = result["access_token"]
                # Token expires_in is in seconds (typically 7200 = 2 hours)
                self._token_expiry = time.time() + result.get("expires_in", 7200)
                _LOGGER.debug("eBay access token refreshed, expires in %s seconds", result.get("expires_in"))

        except aiohttp.ClientError as err:
            _LOGGER.error("Network error during eBay token request: %s", err)
            raise EbayApiError(f"Network error: {err}") from err

    async def search(
        self,
        query: str,
        max_price: float | None = None,
        min_price: float | None = None,
        conditions: list[str] | None = None,
        location_country: str | None = None,
        buying_options: list[str] | None = None,
        category_id: str | None = None,
        limit: int = 50,
        sort: str = "newlyListed",
    ) -> EbaySearchResult:
        """Search eBay for listings matching the criteria."""
        await self._ensure_token()

        # Build filter string
        filters = []

        if conditions:
            cond_str = "|".join(conditions)
            filters.append(f"conditions:{{{cond_str}}}")

        if buying_options:
            opts_str = "|".join(buying_options)
            filters.append(f"buyingOptions:{{{opts_str}}}")

        if max_price is not None or min_price is not None:
            low = f"{min_price:.2f}" if min_price else ""
            high = f"{max_price:.2f}" if max_price else ""
            filters.append(f"price:[{low}..{high}]")
            filters.append("priceCurrency:USD")

        if location_country:
            filters.append(f"itemLocationCountry:{location_country}")

        params: dict[str, str] = {
            "q": query,
            "limit": str(limit),
            "sort": sort,
            "fieldgroups": "MATCHING_ITEMS,EXTENDED",
        }

        if filters:
            params["filter"] = ",".join(filters)

        if category_id:
            params["category_ids"] = category_id

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "X-EBAY-C-MARKETPLACE-ID": self._site,
            "Content-Type": "application/json",
        }

        try:
            async with self._session.get(
                EBAY_SEARCH_URL, headers=headers, params=params
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    _LOGGER.error(
                        "eBay search failed (%s): %s", resp.status, error_text
                    )
                    return EbaySearchResult(
                        total_results=0,
                        error=f"API error {resp.status}",
                    )

                data = await resp.json()

        except aiohttp.ClientError as err:
            _LOGGER.error("Network error during eBay search: %s", err)
            return EbaySearchResult(total_results=0, error=str(err))

        total = data.get("total", 0)
        items = data.get("itemSummaries", [])
        listings = []

        for item in items:
            price_info = item.get("price", {})
            seller_info = item.get("seller", {})
            image_info = item.get("image", {})
            location_info = item.get("itemLocation", {})
            categories = item.get("categories", [{}])

            # Build location string
            loc_parts = []
            if location_info.get("city"):
                loc_parts.append(location_info["city"])
            if location_info.get("stateOrProvince"):
                loc_parts.append(location_info["stateOrProvince"])
            if location_info.get("country"):
                loc_parts.append(location_info["country"])
            location_str = ", ".join(loc_parts) if loc_parts else "Unknown"

            # Determine time remaining for auctions
            time_remaining = None
            item_end_date = item.get("itemEndDate")
            if item_end_date:
                time_remaining = item_end_date  # ISO 8601; we parse in the sensor

            listing = EbayListing(
                item_id=item.get("itemId", ""),
                title=item.get("title", ""),
                price=float(price_info.get("value", 0)),
                currency=price_info.get("currency", "USD"),
                condition=item.get("condition", "Unknown"),
                url=item.get("itemWebUrl", item.get("itemAffiliateWebUrl", "")),
                image_url=image_info.get("imageUrl"),
                seller_name=seller_info.get("username", "Unknown"),
                seller_feedback_percentage=seller_info.get(
                    "feedbackPercentage", "0"
                ),
                seller_feedback_score=int(
                    seller_info.get("feedbackScore", 0)
                ),
                buying_options=item.get("buyingOptions", []),
                bid_count=int(item.get("bidCount", 0)),
                time_remaining=time_remaining,
                item_location=location_str,
                category=categories[0].get("categoryName", "") if categories else "",
            )
            listings.append(listing)

        _LOGGER.debug(
            "eBay search for '%s' returned %d results (%d items parsed)",
            query,
            total,
            len(listings),
        )

        return EbaySearchResult(total_results=total, listings=listings)

    async def validate_credentials(self) -> bool:
        """Test if the API credentials are valid."""
        try:
            await self._ensure_token()
            return True
        except EbayApiError:
            return False


class EbayApiError(Exception):
    """Error communicating with eBay API."""
