# Pico 2W MQTT Client - Project Plan

## Project Overview

MicroPython project for Raspberry Pi Pico 2W integrating with Home Assistant via MQTT. Reads DS18B20 temperature sensors (multiple on single GPIO) and ACS37030 current sensors. Supports wireless code updates via SD card or GitHub.

## Hardware

### Components

| Component | Model | Quantity | Purpose |
|-----------|-------|----------|---------|
| Microcontroller | Raspberry Pi Pico 2W | 1 | Main controller with WiFi |
| Temperature Sensor | DS18B20 waterproof | 2 | Room and water temperature |
| Current Sensor | ACS37030LLZATR-020B3 | 5 | Current measurement (±20A) |
| ADC | ADS1115 | 1 | I2C ADC for current sensors |
| SD Card Module | SPI micro SD | 1 | Code updates storage |
| Push Button | Momentary | 1 | Trigger updates |

### Pin Assignment

| Component | GPIO | Interface | Notes |
|-----------|------|-----------|-------|
| DS18B20 | GP22 | 1-Wire | Shared bus for both sensors |
| ADS1115 SCL | GP5 | I2C1 | Clock |
| ADS1115 SDA | GP4 | I2C1 | Data |
| ACS37030 #5 | GP26 | ADC0 | 5th current sensor |
| SD MOSI | GP15 | SPI0 | Data out |
| SD MISO | GP12 | SPI0 | Data in |
| SD SCK | GP14 | SPI0 | Clock |
| SD CS | GP13 | GPIO | Chip select |
| Update Button | GP10 | GPIO | Pulled HIGH internally |
| Status LED | GP25 | GPIO | Built-in LED |

### Reserved GPIOs

- GPIO 0-22: Available
- GPIO 23-25: Reserved (Flash/WiFi/BT)
- GPIO 26-28: Available
- GPIO 29: Reserved (USB DM)

## Features

### Implemented

- [x] DS18B20 temperature sensing (multiple sensors)
- [x] ACS37030 current sensing (5 sensors via ADS1115)
- [x] MQTT integration with Home Assistant
- [x] Automatic MQTT discovery
- [x] LED control via MQTT
- [x] Internal temperature sensor
- [x] Auto-reconnect (WiFi + MQTT)
- [x] Sensor hot-swap detection
- [x] SD Card code updater
- [x] GitHub WiFi updater
- [x] Manual rollback (double-press)
- [x] Update button in Home Assistant

### SD Card Updater

| Feature | Status |
|---------|--------|
| Single-press update | ✅ |
| Double-press rollback | ✅ |
| Version checking | ✅ |
| Backup before update | ✅ |
| Auto-rollback on failure | ✅ |
| LED feedback patterns | ✅ |
| Sensor folder support | ✅ |

## Software Architecture

### File Structure

```
secondTest/
├── main.py              # Entry point (runs on boot), calls app.main()
├── app.py              # Main MQTT application
├── sd_updater.py       # SD card code updater module
├── github_updater.py   # GitHub WiFi updater
├── config.py           # Configuration constants
├── secrets.py          # WiFi/MQTT credentials (not committed)
├── version.txt         # Current version (reference)
├── blink.py            # LED blink utilities
├── wifi_utils.py       # WiFi connection utilities
├── updater_utils.py    # Shared backup/restore, version, logging
├── sensors/
│   ├── __init__.py     # Sensor imports
│   ├── ds18b20.py      # DS18B20 driver
│   ├── ads1115.py      # ADS1115 I2C ADC driver
│   └── acs37030.py     # ACS37030 current sensor driver
└── .vscode/           # VS Code settings
```

### Update Flow

```
Power on
    │
    ▼
main.py runs (entry point)
    │
    ├── GitHub update check
    │    │
    │    └── Update available? ──► Download ──► Reboot
    │
    ├── SD card update check
    │    │
    │    ├── Double-press (within 2s) ──► Rollback ──► Restore /backup/ ──► Reboot
    │    │
    │    └── Update available? ──► Copy files ──► Reboot
    │
    └── Run app.main() ──► MQTT client, sensors, Home Assistant
```

## MQTT Configuration

### Topics

| Topic | Type | Description |
|-------|------|-------------|
| `homeassistant/sensor/pico/cpu_temp/state` | State | Internal temperature |
| `homeassistant/sensor/pico/cpu_temp/config` | Discovery | Temperature config |
| `homeassistant/sensor/pico/room_temp/state` | State | Room temperature |
| `homeassistant/sensor/pico/room_temp/config` | Discovery | Room temp config |
| `homeassistant/sensor/pico/water_temp/state` | State | Water temperature |
| `homeassistant/sensor/pico/water_temp/config` | Discovery | Water temp config |
| `homeassistant/sensor/pico/current_1-5/state` | State | Current measurements (5 sensors) |
| `homeassistant/sensor/pico/current_1-5/config` | Discovery | Current sensor configs |
| `homeassistant/switch/pico/led/state` | State | LED state |
| `homeassistant/switch/pico/led/set` | Command | LED control |
| `homeassistant/switch/pico/led/config` | Discovery | LED config |
| `homeassistant/button/pico/update/set` | Command | Update button command |
| `homeassistant/button/pico/update/state` | State | Update button state |
| `homeassistant/button/pico/update/config` | Discovery | Update button config |
| `homeassistant/sensor/pico/availability` | State | Device online/offline |

### Publish-If-Changed Pattern

```python
def mqtt_publish(topic: str, value: str, retain: bool = True) -> bool:
    global _last_mqtt_values
    if _last_mqtt_values.get(topic) != value:
        mqtt_client.publish(topic, value, retain=retain)
        _last_mqtt_values[topic] = value
        return True
    return False
```

## Implementation History

### v1.0 - Initial Release
- Basic MQTT client
- DS18B20 temperature sensors
- ISNS20 current sensor
- Home Assistant discovery
- LED control

### v1.1 - Bug Fixes
- Minor improvements

### v1.2 - SD Card Updater
- Added boot.py
- Added sd_updater.py
- Single-press update trigger
- Backup before update
- LED feedback patterns

### v1.3 - Rollback Support
- Double-press rollback trigger
- Improved backup/restore
- Sensor folder support
- LED feedback for all states

## Testing Checklist

- [x] WiFi connects
- [x] MQTT connects to broker
- [x] DS18B20 sensors read correctly
- [x] ACS37030 current sensors read correctly (5 sensors)
- [x] Home Assistant discovers all entities
- [x] LED control works
- [x] Auto-reconnect works
- [x] SD card mounts
- [x] Update trigger works
- [x] Update copies files correctly
- [x] Rollback restores files
- [x] LED patterns display correctly
- [x] GitHub update check works
- [x] Update button in Home Assistant works

## Configuration

### Required Parameters

```python
# WiFi
WIFI_SSID = "YourNetwork"
WIFI_PASSWORD = "YourPassword"

# MQTT
MQTT_BROKER = "broker.example.com"
MQTT_PORT = 8883
MQTT_USER = "username"
MQTT_PASSWORD = "password"
MQTT_SSL = True

# Pins
DS18B20_PIN = 22
ACS37030_I2C_ADDRESS = 0x48
ACS37030_I2C_SCL_PIN = 5
ACS37030_I2C_SDA_PIN = 4
ACS37030_NUM_SENSORS = 5
ACS37030_PICO_ADC_PIN = 26
SD_SCK_PIN = 14
SD_MOSI_PIN = 15
SD_MISO_PIN = 12
SD_CS_PIN = 13
UPDATE_BUTTON_PIN = 10

# GitHub
GITHUB_OWNER = "yourusername"
GITHUB_REPO = "your-repo"
```

## Notes

### Sensor Assignment

Multiple DS18B20 sensors on same GPIO are auto-assigned by discovery order:
- First sensor found (index 0) = Room temperature
- Second sensor found (index 1) = Water temperature

If only one sensor is connected, water_temp shows "unavailable".

ACS37030 current sensors are assigned by channel:
- Channels 0-3 (ADS1115) = Current sensors 1-4
- Channel 4 (Pico ADC) = Current sensor 5

### SD Card Requirements

- Format: FAT32
- Max size: 32GB (recommended)
- Update folder must be named exactly: `update/`

### Timing

- DS18B20 conversion: 750ms
- MQTT keepalive: 30s
- Temperature publish interval: 1000ms
- Sensor retry interval: 60000ms
- Update button window: 2 seconds
- Double-press window: 1 second

### Limitations

- Cannot flash firmware via SD card (requires computer)
- Cannot recover from completely broken state via SD card
- Rollback only restores last version (overwrites previous backup)
