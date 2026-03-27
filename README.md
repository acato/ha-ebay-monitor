# eBay Monitor for Home Assistant

A custom Home Assistant integration that monitors eBay for items matching your search criteria and sends actionable notifications when new listings appear.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/acato/ha-ebay-monitor)](https://github.com/acato/ha-ebay-monitor/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Features

- **Configurable searches** -- define multiple eBay searches with filters for price, condition, seller location, listing type, and category
- **Actionable push notifications** -- tap "View on eBay" or "Buy Now" to open the listing directly on your phone
- **Multi-channel alerts** -- trigger any HA notification service (push, email, SMS, Telegram, etc.)
- **Rich notification data** -- listing title, price, thumbnail image, seller rating, bid count, time remaining
- **Price drop detection** -- re-alerts you when a previously-seen listing drops in price, with previous price, drop amount, and percentage
- **Deduplication** -- tracks seen listings with prices persistently so you only get notified once per item (unless the price changes)
- **Critical deal alerts** -- bypass Do Not Disturb for exceptional prices
- **Daily digest** -- optional summary of active search results
- **Multiple marketplace support** -- US, UK, DE, FR, IT, ES, CA, AU

## Prerequisites

### eBay Developer Account (Free)

You need an eBay Developer Program account to access the Browse API. This is free and takes about 1 business day for approval.

#### Step 1: Register

1. Go to [developer.ebay.com/join](https://developer.ebay.com/join)
2. Sign in with your existing eBay account, or create one
3. Complete the developer registration form
4. Wait for approval (typically within 1 business day)

#### Step 2: Create Application Keys

1. Once approved, go to [developer.ebay.com/my/keys](https://developer.ebay.com/my/keys)
2. Under **Production**, click **Create a keyset** (you need Production keys, not Sandbox)
3. For "Application Title", enter something like "Home Assistant Monitor"
4. For "OAuth Redirect URL", enter `https://localhost` (this won't be used, but the field is required)
5. Note down two values:
   - **App ID (Client ID)** -- looks like `YourName-HomeAssi-PRD-abc123def-456789ab`
   - **Cert ID (Client Secret)** -- looks like `PRD-bc123def456-7890-abcd-ef12-345678901234`

> **Important:** These are your Production keys. The Browse API search endpoint requires Production keys -- Sandbox keys will not return real listings.

#### Step 3: Verify API Access

The Browse API with client credentials grant (application-level token) requires only the `api_scope` scope. This is automatically available -- no special approval needed. Your daily rate limit is approximately 5,000 API calls, which is more than sufficient.

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots menu (top right) and select **Custom repositories**
3. Add this repository URL:
   ```
   https://github.com/acato/ha-ebay-monitor
   ```
4. Select **Integration** as the category
5. Click **Add**
6. Search for "eBay Monitor" in the HACS integrations list
7. Click **Download**
8. **Restart Home Assistant**

### Manual Installation

1. Download the `custom_components/ebay_monitor/` directory from this repository
2. Copy it to your Home Assistant `config/custom_components/` directory:
   ```
   config/
   └── custom_components/
       └── ebay_monitor/
           ├── __init__.py
           ├── config_flow.py
           ├── const.py
           ├── ebay_api.py
           ├── manifest.json
           ├── sensor.py
           ├── binary_sensor.py
           ├── storage.py
           ├── strings.json
           └── translations/
               └── en.json
   ```
3. **Restart Home Assistant**

## Configuration

### Step 1: Add the Integration

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for **eBay Monitor**
3. Enter your eBay API credentials:
   - **App ID (Client ID)** -- from your eBay Developer dashboard
   - **Cert ID (Client Secret)** -- from your eBay Developer dashboard
   - **eBay Marketplace** -- select your market (default: EBAY_US)
4. Click **Submit** -- the integration will validate your credentials against the eBay API

### Step 2: Add Searches

1. After adding the integration, click **Configure** on the eBay Monitor card
2. Select **Add a new search**
3. Fill in the search parameters:

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| Search name | Yes | Unique slug identifier | `nvidia_a100` |
| Search keywords | Yes | eBay search query | `NVIDIA A100 80GB PCIe` |
| Maximum price | No | Upper price limit (USD) | `5000` |
| Minimum price | No | Lower price limit (USD) | `1000` |
| Item condition(s) | No | Filter by condition | `USED` |
| Seller country | No | Restrict to sellers in this country | `US` |
| Listing type(s) | No | Auction, fixed price, or both | `FIXED_PRICE`, `AUCTION` |
| Category ID | No | eBay category ID for precision | `27386` (Computer Components) |
| Scan interval | No | Minutes between checks (default: 15) | `60` (for daily-ish) |

4. Click **Submit**
5. Repeat for additional searches

### Step 3: Set Up Notifications

The integration fires a custom event `ebay_monitor_new_listing` for each new listing found. You create automations that listen for this event and send notifications through whatever channels you want.

#### Basic Push Notification

Create an automation in the HA UI or add to your `automations.yaml`:

```yaml
- id: ebay_monitor_push
  alias: "eBay Monitor - Push Notification"
  mode: queued
  max: 20

  trigger:
    - platform: event
      event_type: ebay_monitor_new_listing

  action:
    - action: notify.mobile_app_YOUR_PHONE
      data:
        title: "eBay Deal: {{ trigger.event.data.search_name }}"
        message: >-
          {{ trigger.event.data.title }}
          ${{ "%.2f" | format(trigger.event.data.price) }}
          ({{ trigger.event.data.condition }})
          Seller: {{ trigger.event.data.seller_name }}
          ({{ trigger.event.data.seller_feedback_percentage }}% feedback)
        data:
          image: "{{ trigger.event.data.image_url }}"
          url: "{{ trigger.event.data.url }}"
          clickAction: "{{ trigger.event.data.url }}"
          actions:
            - action: "URI"
              title: "View on eBay"
              uri: "{{ trigger.event.data.url }}"
            - action: "URI"
              title: "Buy Now"
              uri: "{{ trigger.event.data.url }}"
            - action: "DISMISS"
              title: "Dismiss"
          group: "ebay_{{ trigger.event.data.search_name }}"
          channel: "eBay Alerts"
          importance: high
```

> Replace `notify.mobile_app_YOUR_PHONE` with your actual mobile app notify service. Find yours under **Developer Tools** > **Services** > search for `notify.mobile_app`.

#### Critical Deal Alert (Bypasses Do Not Disturb)

For exceptional prices that warrant an immediate alert:

```yaml
- id: ebay_monitor_critical
  alias: "eBay Monitor - Critical Deal"
  mode: queued
  max: 10

  trigger:
    - platform: event
      event_type: ebay_monitor_new_listing

  condition:
    - condition: template
      value_template: >-
        {{ trigger.event.data.search_name == 'nvidia_a100'
           and trigger.event.data.price | float <= 3000 }}

  action:
    - action: notify.mobile_app_YOUR_PHONE
      data:
        title: "EXCEPTIONAL DEAL"
        message: >-
          {{ trigger.event.data.title }}
          ONLY ${{ "%.2f" | format(trigger.event.data.price) }}!
        data:
          image: "{{ trigger.event.data.image_url }}"
          url: "{{ trigger.event.data.url }}"
          actions:
            - action: "URI"
              title: "BUY NOW"
              uri: "{{ trigger.event.data.url }}"
          push:
            sound:
              name: default
              critical: 1
              volume: 1.0
          ttl: 0
          priority: high
```

#### Multi-Channel (Push + Email + Persistent)

Send to multiple notification channels simultaneously:

```yaml
- id: ebay_monitor_multi
  alias: "eBay Monitor - Multi-Channel"
  mode: queued
  max: 20

  trigger:
    - platform: event
      event_type: ebay_monitor_new_listing

  action:
    # Mobile push
    - action: notify.mobile_app_YOUR_PHONE
      data:
        title: "eBay: {{ trigger.event.data.search_name }}"
        message: >-
          {{ trigger.event.data.title }} -
          ${{ "%.2f" | format(trigger.event.data.price) }}
        data:
          image: "{{ trigger.event.data.image_url }}"
          url: "{{ trigger.event.data.url }}"
          actions:
            - action: "URI"
              title: "View on eBay"
              uri: "{{ trigger.event.data.url }}"

    # Email
    - action: notify.email
      data:
        title: "eBay Alert: {{ trigger.event.data.title }}"
        message: >-
          New listing: {{ trigger.event.data.title }}
          Price: ${{ "%.2f" | format(trigger.event.data.price) }}
          Condition: {{ trigger.event.data.condition }}
          Seller: {{ trigger.event.data.seller_name }}
          View: {{ trigger.event.data.url }}

    # Persistent notification in HA dashboard
    - action: persistent_notification.create
      data:
        title: "eBay: {{ trigger.event.data.title }}"
        message: >-
          **${{ "%.2f" | format(trigger.event.data.price) }}** -
          {{ trigger.event.data.condition }}
          Seller: {{ trigger.event.data.seller_name }}
          [View on eBay]({{ trigger.event.data.url }})
        notification_id: "ebay_{{ trigger.event.data.item_id }}"
```

#### Price Drop Alert

Get notified when a previously-seen listing drops in price:

```yaml
- id: ebay_monitor_price_drop
  alias: "eBay Monitor - Price Drop Alert"
  mode: queued
  max: 20

  trigger:
    - platform: event
      event_type: ebay_monitor_price_drop

  action:
    - action: notify.mobile_app_YOUR_PHONE
      data:
        title: "Price Drop: {{ trigger.event.data.search_name }}"
        message: >-
          {{ trigger.event.data.title }}
          Was ${{ "%.2f" | format(trigger.event.data.previous_price) }}
          Now ${{ "%.2f" | format(trigger.event.data.price) }}
          (-{{ trigger.event.data.drop_percentage }}%)
        data:
          image: "{{ trigger.event.data.image_url }}"
          url: "{{ trigger.event.data.url }}"
          actions:
            - action: "URI"
              title: "View on eBay"
              uri: "{{ trigger.event.data.url }}"
            - action: "URI"
              title: "Buy Now"
              uri: "{{ trigger.event.data.url }}"
          channel: "eBay Price Drops"
          importance: high
```

#### Daily Digest

Get a summary of all active listings once per day:

```yaml
- id: ebay_monitor_digest
  alias: "eBay Monitor - Daily Digest"
  mode: single

  trigger:
    - platform: time
      at: "09:00:00"

  condition:
    - condition: template
      value_template: >-
        {{ state_attr('sensor.ebay_nvidia_a100', 'total_results') | int(0) > 0 }}

  action:
    - action: notify.mobile_app_YOUR_PHONE
      data:
        title: "eBay Daily Digest"
        message: >-
          {% set listings = state_attr('sensor.ebay_nvidia_a100', 'latest_listings') %}
          {% if listings %}
          Top listings:
          {% for item in listings[:5] %}
          - {{ item.title[:60] }} - ${{ "%.0f" | format(item.price) }}
          {% endfor %}
          {% else %}
          No new listings found.
          {% endif %}
```

## Entities

For each configured search, the integration creates:

### Sensor: `sensor.ebay_<search_name>`

| Attribute | Description |
|-----------|-------------|
| **State** | Number of new (unseen) listings from the last scan |
| `total_results` | Total eBay results matching the search |
| `latest_listings` | List of up to 10 most recent listings with full details |
| `search_query` | The search keywords |
| `max_price` | Configured price ceiling |
| `new_listing_ids` | Item IDs of newly found listings |

### Binary Sensor: `binary_sensor.ebay_<search_name>_match`

- **ON** when new unseen listings were found in the last scan
- **OFF** when no new listings were found

## Event Data

The `ebay_monitor_new_listing` event carries this data:

| Field | Type | Description |
|-------|------|-------------|
| `search_name` | string | Which search found this listing |
| `item_id` | string | eBay item ID |
| `title` | string | Listing title |
| `price` | float | Current price |
| `currency` | string | Price currency (e.g., USD) |
| `condition` | string | Item condition |
| `url` | string | Direct link to the listing |
| `image_url` | string | Thumbnail image URL |
| `seller_name` | string | Seller username |
| `seller_feedback_percentage` | string | Seller positive feedback % |
| `seller_feedback_score` | int | Seller feedback count |
| `buying_options` | list | FIXED_PRICE, AUCTION, BEST_OFFER |
| `bid_count` | int | Number of bids (auctions) |
| `time_remaining` | string | Auction end time (ISO 8601) |
| `item_location` | string | Seller location |
| `category` | string | eBay category name |

### Price Drop Event: `ebay_monitor_price_drop`

Fired when a previously-seen listing's price decreases. Contains all the same fields as `ebay_monitor_new_listing`, plus:

| Field | Type | Description |
|-------|------|-------------|
| `previous_price` | float | The price from the last scan |
| `drop_amount` | float | Absolute price decrease |
| `drop_percentage` | float | Percentage decrease |

## How It Works

1. The integration polls the [eBay Browse API](https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search) at your configured interval using application-level OAuth tokens (client credentials grant)
2. Results are sorted by `newlyListed` to catch the freshest listings first
3. Each listing is checked against the persistent store which tracks both item IDs and prices:
   - **New listing** (never seen before) → fires `ebay_monitor_new_listing`
   - **Price drop** (seen before, but price decreased) → fires `ebay_monitor_price_drop`
   - **Unchanged** (same ID, same or higher price) → no event
4. Events are fired on the HA event bus for your automations to handle
5. Your automations listen for these events and route notifications however you want
6. Seen IDs are persisted across HA restarts (rolling window of 1,000 IDs per search)

## Supported Marketplaces

| ID | Marketplace |
|----|-------------|
| `EBAY_US` | United States |
| `EBAY_GB` | United Kingdom |
| `EBAY_DE` | Germany |
| `EBAY_AU` | Australia |
| `EBAY_CA` | Canada |
| `EBAY_FR` | France |
| `EBAY_IT` | Italy |
| `EBAY_ES` | Spain |

## Troubleshooting

### "Invalid credentials" during setup

- Make sure you are using **Production** keys, not Sandbox
- Double-check the App ID and Cert ID at [developer.ebay.com/my/keys](https://developer.ebay.com/my/keys)
- Ensure your developer account has been approved (check your email for confirmation)

### No notifications received

1. Check that your automations are enabled (**Settings** > **Automations**)
2. Verify the event is firing: go to **Developer Tools** > **Events**, listen for `ebay_monitor_new_listing`
3. Check that your `notify.mobile_app_*` service name matches your device
4. Look at HA logs for errors: **Settings** > **System** > **Logs**, filter for `ebay_monitor`

### Listings not updating

- The default scan interval is 15 minutes. Check your configured interval.
- The eBay API token refreshes automatically every 2 hours. If you see auth errors in the logs, verify your credentials.
- Check your eBay Developer dashboard for API quota usage.

### Duplicate notifications

- The deduplication store persists across restarts in `.storage/ebay_monitor_seen.json`
- If you delete this file or clear HA storage, you may get re-notified about previously seen listings on the next scan

## License

MIT License. See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome. Please open an issue or submit a pull request.
