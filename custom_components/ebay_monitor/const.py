"""Constants for the eBay Monitor integration."""

DOMAIN = "ebay_monitor"
PLATFORMS = ["sensor", "binary_sensor"]

# Configuration keys
CONF_APP_ID = "app_id"
CONF_CERT_ID = "cert_id"
CONF_SITE = "site"
CONF_SEARCHES = "searches"
CONF_SEARCH_NAME = "search_name"
CONF_SEARCH_QUERY = "search_query"
CONF_MAX_PRICE = "max_price"
CONF_MIN_PRICE = "min_price"
CONF_CONDITION = "condition"
CONF_LOCATION_COUNTRY = "location_country"
CONF_BUYING_OPTIONS = "buying_options"
CONF_CATEGORY_ID = "category_id"
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults
DEFAULT_SITE = "EBAY_US"
DEFAULT_SCAN_INTERVAL = 15  # minutes
DEFAULT_MAX_SEEN_IDS = 1000

# eBay API endpoints
EBAY_AUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
EBAY_AUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"

# eBay marketplace IDs
EBAY_SITES = {
    "EBAY_US": "EBAY_US",
    "EBAY_GB": "EBAY_GB",
    "EBAY_DE": "EBAY_DE",
    "EBAY_AU": "EBAY_AU",
    "EBAY_CA": "EBAY_CA",
    "EBAY_FR": "EBAY_FR",
    "EBAY_IT": "EBAY_IT",
    "EBAY_ES": "EBAY_ES",
}

# Condition values (eBay Browse API)
CONDITION_NEW = "NEW"
CONDITION_USED = "USED"
CONDITION_REFURBISHED = "REFURBISHED"
CONDITION_UNSPECIFIED = "UNSPECIFIED"

CONDITIONS = [CONDITION_NEW, CONDITION_USED, CONDITION_REFURBISHED, CONDITION_UNSPECIFIED]

# Buying option values
BUYING_FIXED_PRICE = "FIXED_PRICE"
BUYING_AUCTION = "AUCTION"
BUYING_BEST_OFFER = "BEST_OFFER"

BUYING_OPTIONS = [BUYING_FIXED_PRICE, BUYING_AUCTION, BUYING_BEST_OFFER]

# Events
EVENT_NEW_LISTING = f"{DOMAIN}_new_listing"
EVENT_PRICE_DROP = f"{DOMAIN}_price_drop"

# Storage
STORAGE_KEY = f"{DOMAIN}_seen"
STORAGE_VERSION = 1
