# Pico 2W MQTT Client with Home Assistant Integration

MicroPython project for Raspberry Pi Pico 2W that integrates with Home Assistant via MQTT. Reads DS18B20 temperature sensors and ACS37030 current sensors. Supports wireless OTA firmware updates via GitHub with automatic update notifications.

## Features

- **Temperature Sensing**: Two DS18B20 temperature sensors on single GPIO (room + water)
- **Current Sensing**: Up to 5x ACS37030LLZATR-020B3 (±20A) current sensors via ADS1115 I2C
- **Home Assistant Integration**: Automatic MQTT discovery for all sensors
- **LED Control**: Control Pico LED via MQTT
- **Internal Temperature**: RP2350 internal temperature sensor
- **Auto-Reconnect**: WiFi and MQTT with exponential backoff
- **Sensor Hot-Swap**: Automatic detection of connected/disconnected sensors
- **OTA Updates via GitHub**: Auto-update from GitHub releases with progress tracking
- **HA Update Entity**: Native Home Assistant update entity with progress display
- **GitHub Webhook**: Automatic notification when new release is available
- **Rollback**: Restore previous version if update fails

## Hardware

- Raspberry Pi Pico 2W (RP2350)
- 2x DS18B20 temperature sensors (waterproof probes recommended)
- 5x ACS37030LLZATR-020B3 (±20A) current sensors
- 1x ADS1115 4-channel I2C ADC
- 1x push button (for rollback trigger)
- 1x 4.7kΩ resistor (for DS18B20 data line pull-up)

### GPIO Configuration

| Sensor | GPIO | Notes |
|--------|------|-------|
| DS18B20 (both) | GP22 | 1-Wire bus, supports multiple sensors |
| ADS1115 SCL | GP5 | I2C1 Clock |
| ADS1115 SDA | GP4 | I2C1 Data |
| ACS37030 #5 | GP26 | Pico ADC for 5th current sensor |
| SD Card MOSI | GP15 | SPI Data Out |
| SD Card MISO | GP12 | SPI Data In |
| SD Card SCK | GP14 | SPI Clock |
| SD Card CS | GP13 | Chip Select |
| Update Button | GP10 | Pulled HIGH internally |

### DS18B20 Wiring (Daisy-Chained)

Connect both DS18B20 sensors to the same GPIO using a single pull-up resistor:

```
Pico GP22 ────────[4.7kΩ]─────── VCC (3.3V)
                  │
        ┌─────────┴─────────┐
        │                   │
       DQ                  DQ
    Sensor 1            Sensor 2
    (red) VCC          (red) VCC
    (black) GND        (black) GND
```

All sensors share:
- **Data (DQ)**: GP22
- **VCC**: 3V3
- **GND**: GND

### ACS37030 Current Sensor Wiring (via ADS1115)

The project supports up to 5 ACS37030LLZATR-020B3 (±20A) current sensors:
- 4 sensors via ADS1115 I2C ADC (channels A0-A3)
- 1 sensor via Pico's built-in ADC (GP26)

#### ADS1115 Wiring

| ADS1115 | Pico Pin |
|---------|----------|
| VDD | 3V3 |
| GND | GND |
| SCL | GP5 (I2C1 SCL) |
| SDA | GP4 (I2C1 SDA) |
| A0 | ACS37030 #1 VOUT |
| A1 | ACS37030 #2 VOUT |
| A2 | ACS37030 #3 VOUT |
| A3 | ACS37030 #4 VOUT |

#### ACS37030 #5 Wiring (Pico ADC)

| ACS37030 #5 | Pico Pin |
|-------------|----------|
| VDD | 3V3 |
| GND | GND |
| VOUT | GP26 (ADC0) |

#### ACS37030 Pinout

Each ACS37030 has these pins:
| Pin | Function |
|-----|----------|
| VDD | 3.3V |
| GND | Ground |
| VOUT | Analog output (0.33V at -20A, 1.65V at 0A, 2.97V at +20A) |
| VREF | Reference (optional) |

The current path (IP+/IP-) is used to pass the wire to measure current.

## GitHub OTA Updates

### Overview

The Pico can automatically check GitHub for new releases and update itself over WiFi. No computer needed!

### How It Works

```
Boot
    │
    ├─ GitHub Check
    │     │
    │     └─ Newer release? → Download → Write → Reboot
    │
    └─ Continue to app.main()
```

### Update Process

1. **Pico boots** → reads current version from flash
2. **Publishes to HA** → sends version to Home Assistant
3. **GitHub Webhook** → notifies HA when new release is available
4. **HA shows "Update available"** → user clicks "Update installieren"
5. **Pico downloads & updates** → shows progress in HA
6. **Reboots** → with new firmware

### LED Feedback Patterns

| Pattern | Meaning |
|---------|---------|
| "10" | WiFi Connecting |
| "1010" | WiFi Connected (normal) |
| "111" | Failed |
| "11" | Checking GitHub |
| "11011" | Update complete, rebooting |

### Setup

1. **Make repo public**
2. **Create GitHub releases** with version tags (e.g., v1.7)
3. **Attach files** to release:
   - main.py
   - app.py
   - config.py
   - blink.py
   - wifi_utils.py
   - updater_utils.py
   - github_updater.py
   - sensors/__init__.py
   - sensors/ds18b20.py
   - sensors/ads1115.py
   - sensors/acs37030.py
   - version.txt (optional)

### Creating a GitHub Release

1. Go to your repo
2. Click **Create a new release**
3. Tag version: `1.2.3`
4. Release title: `1.2.3 - changes`
5. Attach files by uploading them
6. Click **Publish release**

### Home Assistant Integration

#### HA Automation for Webhook

Create this automation in Home Assistant:

```yaml
automation:
  - alias: "GitHub Release → Pico Update"
    trigger:
      - platform: webhook
        webhook_id: github_update_pico
    action:
      - service: mqtt.publish
        data:
          topic: homeassistant/pico/update/latest_version
          payload: "{{ trigger.json.release.tag_name }}"
          retain: true
```

#### GitHub Webhook Configuration

1. Go to your GitHub repo → Settings → Webhooks
2. Add webhook:
   - **Payload URL**: `https://your-ha-domain.duckdns.org:8123/api/webhook/github_update_pico`
   - **Content type**: application/json
   - **Events**: Releases only

### Configuration

Edit `config.py` to set your GitHub repo:

```python
GITHUB_OWNER = "your-username"
GITHUB_REPO = "your-repo"
```

### Safety Features

- Version comparison (won't downgrade)
- Backup before update
- Auto-rollback on failure

### Notes

- Repository must be **public** (or use GitHub token)
- Files must be attached to the release
- Version format: `v1.x.x` (e.g., v1.7)

## Installation

### 1. Prepare Pico

Flash MicroPython to your Pico 2W:
```bash
# Download uf2 from https://micropython.org/download/
# Hold BOOT button, connect USB, drag uf2 to RPI-RP2
```

### 2. Configure Credentials

Copy `config.py` to `secrets.py` and fill in your WiFi and MQTT credentials:

```python
# secrets.py
WIFI_SSID = "YourNetwork"
WIFI_PASSWORD = "YourPassword"
MQTT_BROKER = "192.168.1.100"
MQTT_PORT = 8883
MQTT_USER = "mqtt_user"
MQTT_PASSWORD = "mqtt_password"
```

### 3. Upload to Pico

Using MicroPico (VS Code extension):
```bash
micropico connect
%send main.py
%send sd_updater.py
%send github_updater.py
%send blink.py
%send wifi_utils.py
%send updater_utils.py
%send app.py
%send config.py
%send secrets.py
%send -r sensors/
```

Or using mpremote:
```bash
mpremote cp main.py :
mpremote cp sd_updater.py :
mpremote cp github_updater.py :
mpremote cp blink.py :
mpremote cp wifi_utils.py :
mpremote cp updater_utils.py :
mpremote cp app.py :
mpremote cp config.py :
mpremote cp secrets.py :
mpremote cp -r sensors/ :
```

### 4. Run

The Pico will automatically run `main.py` on power-up, which then runs `app.main()`.

## MQTT Topics

### State Topics

| Topic | Description |
|-------|-------------|
| `homeassistant/sensor/pico/cpu_temp` | Internal temperature (°C) |
| `homeassistant/sensor/pico/room_temp` | Room temperature (°C) |
| `homeassistant/sensor/pico/water_temp` | Water temperature (°C) |
| `homeassistant/sensor/pico/current_1-4` | Current measurements (A) |
| `homeassistant/switch/pico/led` | LED state (ON/OFF) |

### Update Entity Topics

| Topic | Description |
|-------|-------------|
| `homeassistant/pico/update/state` | Update state (JSON with version info) |
| `homeassistant/pico/update/cmd` | Update command (trigger update) |
| `homeassistant/pico/update/latest_version` | Latest version from GitHub webhook |
| `homeassistant/pico/availability` | Device availability (online/offline) |

### Control Topics

| Topic | Payload | Description |
|-------|---------|-------------|
| `homeassistant/switch/pico/led/set` | `ON` / `OFF` | Control LED |
| `homeassistant/pico/update/cmd` | `PRESS` | Trigger update from HA |

## Home Assistant

The device is automatically discovered via MQTT discovery. After running, you should see:

- `sensor.pico_temperature` - Internal temperature
- `sensor.pico_room_temperature` - Room temperature
- `sensor.pico_water_temperature` - Water temperature
- `sensor.pico_current_1` - Current sensor 1
- `sensor.pico_current_2` - Current sensor 2
- `sensor.pico_current_3` - Current sensor 3
- `sensor.pico_current_4` - Current sensor 4
- `switch.pico_led` - LED control
- `update.pico_firmware` - Firmware update entity (with progress)

## Troubleshooting

### Sensor Not Found
- Check wiring and pull-up resistor (4.7kΩ for DS18B20)
- Verify GPIO pin in config.py (GP22)
- Check Serial output for error messages
- Ensure sensors have unique ROM codes (DS18B20 has built-in unique IDs)

### MQTT Connection Failed
- Verify broker address and port
- Check SSL settings (port 8883 for TLS)
- Ensure firewall allows MQTT ports

### ISNS20 Reading Wrong (Deprecated)
- This sensor is no longer supported. Use ACS37030 instead.

### ACS37030 Reading Wrong
- Verify ADS1115 I2C wiring (SCL=GP5, SDA=GP4)
- Check 3.3V power to both ADS1115 and ACS37030
- Verify ACS37030 sensitivity (66 mV/A for ±20A version)
- Zero current should read ~1.65V on VOUT

### Temperature Sensors Swap
- First sensor found = room temp
- Second sensor found = water temp
- Sensors are auto-assigned by discovery order

## Project Structure

```
secondTest/
├── main.py             # Entry point (runs on boot), calls app.main()
├── app.py              # Main application
├── github_updater.py   # GitHub WiFi updater
├── blink.py            # Shared LED blink utilities
├── wifi_utils.py       # Shared WiFi connection utilities
├── updater_utils.py    # Shared backup/restore, version, logging
├── config.py           # Configuration
├── secrets.py          # WiFi/MQTT credentials
├── sensors/
│   ├── __init__.py
│   ├── ds18b20.py     # DS18B20 temperature sensor driver
│   ├── ads1115.py     # ADS1115 I2C ADC driver
│   └── acs37030.py    # ACS37030 current sensor driver
└── .vscode/           # VS Code settings
```
│   └── acs37030.py    # ACS37030 current sensor driver
└── .vscode/           # VS Code settings
```

## License

MIT
