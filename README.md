# Dyness Battery – Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/shopf/dyness_battery.svg)](https://github.com/shopf/dyness_battery/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A community integration for Home Assistant for **Dyness Battery Storage** via the Dyness Cloud API.

> **Note:** This integration uses the Dyness Open API (Cloud). An internet connection is required. Data is updated every 5 minutes (API limit).

---

### Supported Devices

| Device | Status |
|--------|--------|
| Dyness Junior Box | ✅ Tested |
| Dyness Tower (T14 / non-pro) | ✅ Tested (with advanced sensors) |
| Dyness DL5.0C | ✅ Should work (community-tested) |
| Dyness PowerHaus | ✅ Should work (community-tested) |
| Other Dyness models with WiFi dongle | ⚠️ Not tested – feedback welcome |

> The integration automatically detects the device via the API and only registers sensors available for that specific device.

### Available Sensors

The following sensors are available for all devices:

| Sensor | Description | Unit |
|--------|-------------|------|
| State of Charge (SOC) | Current battery level | % |
| Power | Charge/discharge power (+ = charging, − = discharging) | W |
| Current | Charge/discharge current | A |
| Battery Status | Charging / Discharging / Standby | – |

Additional sensors are automatically enabled if the device provides the data:

| Sensor | Description | Unit | Junior Box | Tower | DL5.0C | PowerHaus |
|--------|-------------|------|:---:|:---:|:---:|:---:|
| Pack Voltage | Total battery pack voltage | V | ✅ | – | ✅ | ✅ |
| State of Health (SOH) | Battery health | % | ✅ | ✅ | ✅ | ✅ |
| Temperature Max | Highest cell temperature | °C | ✅ | ✅ | ✅ | ✅ |
| Temperature Min | Lowest cell temperature | °C | ✅ | ✅ | ✅ | ✅ |
| Cell Voltage Max | Highest individual cell voltage | V | ✅ | ✅ | ✅ | ✅ |
| Cell Voltage Min | Lowest individual cell voltage | V | ✅ | ✅ | ✅ | ✅ |
| Cell Voltage Spread | Max − Min cell voltage (health indicator) | mV | ✅ | ✅ | ✅ | ✅ |
| Energy Charged Today | Energy charged today | kWh | ✅ | – | ✅ | ✅ |
| Energy Discharged Today | Energy discharged today | kWh | ✅ | – | ✅ | ✅ |
| Energy Charged Total | Cumulative energy charged | kWh | ✅ | ✅ | ✅ | ✅ |
| Energy Discharged Total | Cumulative energy discharged | kWh | ✅ | – | ✅ | ✅ |
| Cycle Count | Number of charge cycles | – | – | ✅ | – | ✅ |
| Usable Capacity | Capacity × SOH | kWh | ✅ | ✅ | ✅ | ✅ |
| Energy Remaining | Usable capacity × SOC | kWh | ✅ | ✅ | ✅ | ✅ |
| MOSFET Temperature | MOSFET temperature | °C | ✅ | – | ✅ | ✅ |
| BMS Temperature Max | BMS temperature max | °C | ✅ | – | ✅ | ✅ |
| BMS Temperature Min | BMS temperature min | °C | ✅ | – | ✅ | ✅ |
| Alarm Status | Overall alarm (0 = OK) | – | ✅ | – | ✅ | ✅ |
| **Advanced Tower Diagnostics** | | | | | | |
| Charge / Discharge Limit | Dynamic BMS current limits | A | – | ✅ | – | – |
| Thermal Status | Active fan & heating statuses | – | – | ✅ | – | – |
| Cell Box Locations | Physical box of min/max cells | – | – | ✅ | – | – |

The following sensors are available under **Diagnostics** on the device page:

| Sensor | Description |
|--------|-------------|
| Last Update | Timestamp of last data transmission |
| Battery Capacity | Installed capacity per API |
| Communication Status | Online / Offline |
| Work Status | e.g. RunMode, StandBy, Charging |
| Firmware Version | Current firmware version |

### Prerequisites

1. Dyness Battery is already set up in the **Dyness App** and online.

### Step 1: Create API credentials in the Dyness Portal

1. Open **Dyness User Smart Monitoring** [https://ems.dyness.com/login](https://ems.dyness.com/login) in your browser.
2. Log in with your Dyness account (same as the app).
3. Select **Developer Center** and then **API Management** from the left menu.
4. Click **Create API Key**.
5. Note down your **App ID** and **App Secret** – the secret is only shown once!

### Installation

#### Via HACS (recommended)

1. Open HACS in Home Assistant.
2. Click **Integrations** → **⋮** → **Custom repositories**.
3. Add URL: `https://github.com/your-username/dyness_battery` — Category: **Integration** *(Note: Replace 'your-username' with your actual GitHub name).*
4. Search for **Dyness Battery** and install.
5. Restart Home Assistant.

#### Manual Installation

1. Download the ZIP from [Releases](https://github.com/shopf/dyness_battery/releases).
2. Extract and copy the `custom_components/dyness_battery/` folder to your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.

### Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Dyness Battery**.
3. Enter only your **API ID** and **API Secret** — the device is discovered automatically.

| Field | Description | Example |
|-------|-------------|---------|
| API ID | Your Dyness API ID | `abc123xyz` |
| API Secret | Your Dyness API Secret | `secretkey456` |

> **Multiple batteries:** If you have multiple batteries on one account, the first detected BMS is used automatically. To add further batteries, simply add the integration again with the same credentials.

### API Rate Limit & Scan Interval

The Dyness Cloud API allows approximately 60 requests per hour. The integration automatically adjusts the update interval based on the number of detected battery modules:

| Modules | Interval |
|---------|----------|
| 1–2 | 5 minutes |
| 3–4 | 10 minutes |
| 5+ | 15 minutes |

### Known Limitations

- **Monitoring only** – Control (charge schedules, SOC limits) is not supported via the API.
- **5-minute interval** – The API provides data in 5-minute increments.
- **Cloud dependent** – No local connection (the WiFi dongle is built-in and closed).

### Adding a New Model

Do you have a different Dyness model with a WiFi dongle and want to test it? Open an [Issue](https://github.com/shopf/dyness_battery/issues) with the following information:

- Model name (e.g. `Tower T14`)
- Output of the API test script (see `tools/dyness_test.py`)

---

## Technical Details

Uses the **Dyness Open API v1.1** with HmacSHA1 authentication.

Endpoints used:
- `POST /v1/device/storage/list` – Auto-discover device SN
- `POST /v1/device/bindSn` – Bind device to API key
- `POST /v1/device/getLastPowerDataBySn` – Current power data (every 5 min)
- `POST /v1/device/realTime/data` – Real-time BMS data: pack voltage, SOH, temperatures, cell voltages, energy totals, voltage spread (every 5 min)
- `POST /v1/station/info` – Station info (battery capacity)
- `POST /v1/device/household/storage/detail` – Device details (firmware, status)

---

## Contributing

Pull requests and issues are welcome! Especially needed:
- Testing with other Dyness models
- Improvements to sensor data mapping

## Community & Support

| | |
|---|---|
| 💬 **Questions & Ideas** | [GitHub Discussions](https://github.com/shopf/dyness_battery/discussions) |
| 🐛 **Bug Reports** | [GitHub Issues](https://github.com/shopf/dyness_battery/issues) |
| 🔌 **New Device** | Open an Issue with your `dyness_test.py` output |

---

## License

MIT License – see [LICENSE](LICENSE)
