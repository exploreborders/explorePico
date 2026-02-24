# Pico 2W MQTT Client - Project Plan

## Project Overview

MicroPython project for Raspberry Pi Pico 2W integrating with Home Assistant via MQTT. Reads DS18B20 temperature sensors (multiple on single GPIO) and Pmod ISNS20 current sensor. Supports wireless code updates via SD card.

## Hardware

### Components

| Component | Model | Quantity | Purpose |
|-----------|-------|----------|---------|
| Microcontroller | Raspberry Pi Pico 2W | 1 | Main controller with WiFi |
| Temperature Sensor | DS18B20 waterproof | 2 | Room and water temperature |
| Current Sensor | Pmod ISNS20 | 1 | Current measurement (20A) |
| SD Card Module | SPI micro SD | 1 | Code updates storage |
| Push Button | Momentary | 1 | Trigger updates |

### Pin Assignment

| Component | GPIO | Interface | Notes |
|-----------|------|-----------|-------|
| DS18B20 | GP22 | 1-Wire | Shared bus for both sensors |
| ISNS20 CS | GP8 | SPI0 | Chip select |
| ISNS20 SCK | GP2 | SPI0 | Clock |
| ISNS20 MOSI | GP3 | SPI0 | Data out |
| ISNS20 MISO | GP4 | SPI0 | Data in |
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
- [x] ISNS20 current sensing
- [x] MQTT integration with Home Assistant
- [x] Automatic MQTT discovery
- [x] LED control via MQTT
- [x] Internal temperature sensor
- [x] Auto-reconnect (WiFi + MQTT)
- [x] Sensor hot-swap detection
- [x] SD Card code updater
- [x] Manual rollback (double-press)

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
├── boot.py              # Entry point, calls sd_updater then main
├── sd_updater.py       # SD card code updater module
├── main.py             # Main MQTT application
├── config.py           # Configuration constants
├── secrets.py          # WiFi/MQTT credentials (not committed)
├── version.txt         # Current version (reference)
├── sensors/
│   ├── __init__.py     # Sensor imports
│   ├── ds18b20.py      # DS18B20 driver
│   └── isns20.py       # ISNS20 driver
└── .vscode/           # VS Code settings
```

### Update Flow

```
Power on
    │
    ▼
boot.py runs
    │
    ├── Double-press (within 2s) ──► Rollback ──► Restore /backup/ ──► Reboot
    │
    ├── Single-press ──► Update ──► Mount SD ──► Check version
    │                              │
    │                              ├── Version higher? ──► Backup ──► Copy files ──► Reboot
    │                              │
    │                              └── Version same/lower ──► Skip
    │
    └── No press ──► Run main.py
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
| `homeassistant/sensor/pico/current/state` | State | Current measurement |
| `homeassistant/sensor/pico/current/config` | Discovery | Current config |
| `homeassistant/switch/pico/led/state` | State | LED state |
| `homeassistant/switch/pico/led/set` | Command | LED control |
| `homeassistant/switch/pico/led/config` | Discovery | LED config |

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
- [x] ISNS20 current reads correctly
- [x] Home Assistant discovers all entities
- [x] LED control works
- [x] Auto-reconnect works
- [x] SD card mounts
- [x] Update trigger works
- [x] Update copies files correctly
- [x] Rollback restores files
- [x] LED patterns display correctly

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
ISNS20_CS_PIN = 8
ISNS20_SPI_PORT = 0
SD_SCK_PIN = 14
SD_MOSI_PIN = 15
SD_MISO_PIN = 12
SD_CS_PIN = 13
UPDATE_BUTTON_PIN = 10
```

## Notes

### Sensor Assignment

Multiple DS18B20 sensors on same GPIO are auto-assigned by discovery order:
- First sensor found (index 0) = Room temperature
- Second sensor found (index 1) = Water temperature

If only one sensor is connected, water_temp shows "unavailable".

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
