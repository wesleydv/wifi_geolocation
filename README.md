# WiFi Geolocation

A Home Assistant custom integration that provides WiFi-based geolocation for device trackers without GPS. Uses Google Geolocation API to determine location from WiFi access point data.

## What Does This Integration Do?

This integration adds WiFi-based geolocation capabilities to Home Assistant device trackers. It's designed to work with devices that can scan for WiFi networks but don't have GPS capabilities or prefer wifi scans over GPS calls to save on battery (like a SenseCap T1000).

**How it works:**
1. Monitors device tracker entities for WiFi access point data (MAC addresses and signal strength)
2. When new WiFi data is detected, automatically sends it to Google Geolocation API
3. Receives location coordinates based on WiFi network triangulation
4. Updates the device tracker with the geocoded location
5. Caches results to minimize API calls and costs

**Key Features:**
- **Automatic operation** - No automations needed, works out of the box
- **Smart caching** - Reuses location data for known WiFi combinations
- **GPS fallback** - Uses GPS when available, WiFi geolocation when not
- **Persistent storage** - Cached locations survive restarts
- **Change detection** - Only calls API when WiFi environment changes

## Setup

### 1. Get a Google Geolocation API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a new API key (or use an existing one)
3. Enable the "Geolocation API" for your project
4. Copy your API key

### 2. Install the Integration

1. Copy the `wifi_geolocation` folder to your `custom_components` directory
2. Restart Home Assistant
3. Go to **Settings** → **Devices & Services** → **Add Integration**
4. Search for "WiFi Geolocation"
5. Enter your Google Geolocation API key

### 3. Configure Your Device Trackers

The integration works automatically with any device tracker entity that provides WiFi access point data in the `wifi_access_points` attribute.

**Supported format:**
```json
{
  "wifi_access_points": [
    {
      "macAddress": "AA:BB:CC:DD:EE:FF",
      "signalStrength": -45
    },
    {
      "macAddress": "11:22:33:44:55:66",
      "signalStrength": -67
    }
  ]
}
```

## Usage

### Automatic Geolocation

Once configured, the integration works automatically:

1. Monitors all device tracker entities
2. Detects when `wifi_access_points` attribute changes
3. Automatically calls Google Geolocation API
4. Updates the device tracker with the geocoded location

**No manual automation required!**

### Manual Service Call

You can manually trigger geolocation via Developer Tools → Services:

```yaml
service: wifi_geolocation.geolocate
data:
  entity_id: device_tracker.my_device
  force: false  # Set to true to bypass cache
```

### Understanding the Results

The integration adds the following attributes to device trackers:

- `geocoded_latitude` - Latitude from WiFi geolocation
- `geocoded_longitude` - Longitude from WiFi geolocation
- `geocoded_accuracy` - Accuracy radius in meters
- `location_source` - Either "gps" or "geocoded" (indicates which is currently shown)

**Priority:** If the device has GPS coordinates, those take precedence. If no GPS, the geocoded WiFi location is used.

## Caching System

The integration uses a smart caching system to minimize API calls:

### How Caching Works

1. **BSSID Combination Cache** - Each unique set of WiFi access points (BSSIDs) is cached with its location
2. **Change Detection** - Only calls API when the set of visible access points changes
3. **Persistent Storage** - Cache survives Home Assistant restarts

### Cache Location

Cached data is stored in `.storage/wifi_geolocation`

**Example cache format:**
```json
{
  "location_cache": {
    "AA:BB:CC:DD:EE:FF|11:22:33:44:55:66": {
      "latitude": 37.7749,
      "longitude": -122.4194,
      "accuracy": 25.0
    }
  }
}
```

### Managing the Cache

**View cached locations:**
```bash
cat config/.storage/wifi_geolocation
```

**Clear cache** (force fresh API calls):
```bash
rm config/.storage/wifi_geolocation
# Then restart Home Assistant
```

## Service Reference

### `wifi_geolocation.geolocate`

Manually trigger geolocation for a device tracker.

**Parameters:**
- `entity_id` (required) - Device tracker entity with `wifi_access_points` attribute
- `force` (optional, default: false) - Force API call even if location is cached

**Example:**
```yaml
service: wifi_geolocation.geolocate
data:
  entity_id: device_tracker.my_device
  force: true
```

## How It Saves API Calls

The integration is designed to minimize Google API usage:

1. **Same WiFi as before?** → Skip (device hasn't moved)
2. **Same WiFi combination as cached location?** → Use cached coordinates (no API call)
3. **New WiFi combination?** → Call API and cache the result

Set `force: true` to override caching and force a fresh API call.

## Troubleshooting

### Integration not appearing

- Restart Home Assistant after copying files
- Check logs for errors: `Settings` → `System` → `Logs`

### "No wifi_access_points attribute" error

The device tracker must provide WiFi access point data. This integration is designed to work with The Things Network device trackers that include WiFi scanning capability.

### API key errors

- Verify the API key is correct
- Check that "Geolocation API" is enabled in Google Cloud Console
- Verify billing is enabled (Google requires a billing account even for free tier)

### Location not updating

- Check that the WiFi access points are actually changing
- View logs to see if cache is being used
- Try `force: true` to bypass cache

## Development Roadmap

### Completed
- ✅ Config flow for API key configuration
- ✅ Automatic geolocation on WiFi changes
- ✅ Smart caching system
- ✅ Persistent storage
- ✅ BSSID change detection

### Planned Features
- ⏳ Options flow for configuration
  - Enable/disable automatic geolocation
  - BSSID sensitivity threshold
  - Cache management
- ⏳ Cache statistics and monitoring
- ⏳ Support for multiple geolocation providers (Mozilla Location Service, etc.)
- ⏳ Partial BSSID matching for incremental location updates

## Technical Details

### Architecture

- **Entry point:** `async_setup_entry` - Configures integration from config entry
- **Service handler:** `async_geolocate` - Processes geolocation requests
- **State listener:** `async_state_changed_listener` - Monitors device trackers
- **API client:** `_call_geolocation_api` - Communicates with Google API
- **Storage:** Home Assistant's Store API for persistent caching

### Data Flow

```
Device Tracker WiFi Update
    ↓
State Change Listener
    ↓
Check if WiFi changed
    ↓
Check location cache
    ↓
Call Google API (if needed)
    ↓
Update device tracker location
    ↓
Save to cache
```
