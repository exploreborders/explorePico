# Pico 2W MQTT Client - Project Plan

## Project Overview

MicroPython project for Raspberry Pi Pico 2W integrating with Home Assistant via MQTT. Reads DS18B20 temperature sensors and ACS37030 current sensors via ADS1115. Supports OTA firmware updates via GitHub with Home Assistant native Update Entity.

## Hardware

### Components

| Component | Model | Quantity | Purpose |
|-----------|-------|----------|---------|
| Microcontroller | Raspberry Pi Pico 2W | 1 | Main controller with WiFi |
| Temperature Sensor | DS18B20 waterproof | 2 | Room and water temperature |
| Current Sensor | ACS37030LLZATR-020B3 | 5 | Current measurement (±20A) |
| ADC | ADS1115 | 1 | I2C ADC for current sensors 1-4 |
| Push Button | Momentary | 1 | Trigger rollback at boot |

### Pin Assignment

| Component | GPIO | Interface | Notes |
|-----------|------|-----------|-------|
| DS18B20 | GP22 | 1-Wire | Shared bus for both sensors |
| ADS1115 SCL | GP5 | I2C1 | Clock |
| ADS1115 SDA | GP4 | I2C1 | Data |
| ACS37030 #5 | GP26 | ADC0 | 5th current sensor |
| ACS37030 #5 | GP26 | ADC0 | 5th current sensor (optional) |
| Update Button | GP10 | GPIO | Pulled HIGH internally |
| Status LED | GP25 | GPIO | Built-in LED (WLED on Pico W) |

### Reserved GPIOs

- GPIO 0-22: Available
- GPIO 23-25: Reserved (Flash/WiFi/BT)
- GPIO 26-28: Available (ADC0-2)
- GPIO 29: Reserved (USB DM)

## Features

### Implemented

- [x] DS18B20 temperature sensing (multiple sensors on single GPIO)
- [x] ACS37030 current sensing (4 sensors via ADS1115 I2C, 1 via Pico ADC)
- [x] Internal RP2350 temperature sensor
- [x] MQTT integration with Home Assistant
- [x] Automatic MQTT discovery (all sensors auto-detected)
- [x] LED control via MQTT
- [x] Auto-reconnect (WiFi + MQTT) with exponential backoff
- [x] Sensor hot-swap detection (DS18B20)
- [x] GitHub WiFi OTA updater
- [x] Manual rollback (double-press update button at boot)
- [x] HA Update Entity with progress tracking
- [x] GitHub webhook support for update notifications

### Update Flow

```
Power on
    │
    ▼
main.py runs (entry point)
    │
    ├── Check rollback trigger (double-press within 2s)
    │    └── Rollback ──► Restore /backup/ ──► Reboot
    │
    ├── GitHub update check (if WiFi available)
    │    └── Update available? ──► Download ──► Write ──► Reboot
    │
    └── Run app.main() ──► MQTT client, sensors, Home Assistant
```

## Software Architecture

### File Structure

```
secondTest/
├── main.py              # Entry point (runs on boot), handles updates
├── app.py              # Main MQTT application (769 lines)
├── github_updater.py   # GitHub WiFi OTA updater
├── config.py           # Configuration constants
├── secrets.py          # WiFi/MQTT credentials (not committed)
├── blink.py            # LED blink utilities
├── wifi_utils.py       # WiFi connection utilities
├── updater_utils.py    # Shared backup/restore, version, logging
└── sensors/
    ├── __init__.py     # Sensor imports
    ├── ds18b20.py      # DS18B20 driver + DS18B20Manager
    ├── ads1115.py      # ADS1115 I2C ADC driver
    └── acs37030.py     # ACS37030 current sensor driver
```

### Key Design Patterns

#### Sensor Manager Pattern
```python
sensor = DS18B20(DS18B20_PIN)
manager = DS18B20Manager(sensor, "DS18B20", retry_interval_ms=60000)
manager.set_logger(log)
temps = manager.read(TEMP_CONVERSION_TIME_MS)
```

#### MQTT Publish-If-Changed
```python
_last_mqtt_values = {}

def mqtt_publish(topic: str, value: str, retain: bool = True) -> bool:
    global _last_mqtt_values
    key = (topic, retain)
    if _last_mqtt_values.get(key) != value:
        mqtt_client.publish(topic, value, retain=retain)
        _last_mqtt_values[key] = value
        return True
    return False
```

#### HA Update Entity
```python
# Config payload
{
    "platform": "update",
    "state_topic": TOPIC_UPDATE_STATE,
    "command_topic": TOPIC_UPDATE_CMD,
    "payload_install": "PRESS",
}

# State payload (JSON)
{
    "installed_version": "1.0",
    "latest_version": "1.1",
    "in_progress": false,
    "update_percentage": 65
}
```

## MQTT Topics

| Topic | Type | Description |
|-------|------|-------------|
| `homeassistant/pico/sensor/cpu_temp` | State | Internal temperature |
| `homeassistant/pico/sensor/room_temp` | State | Room temperature (DS18B20 #1) |
| `homeassistant/pico/sensor/water_temp` | State | Water temperature (DS18B20 #2) |
| `homeassistant/pico/sensor/current_1-5` | State | Current measurements |
| `homeassistant/pico/switch/led/state` | State | LED state |
| `homeassistant/pico/switch/led/set` | Command | LED control |
| `homeassistant/pico/update/state` | State | Update entity state (JSON) |
| `homeassistant/pico/update/cmd` | Command | Update trigger |
| `homeassistant/pico/update/latest_version` | Command | Latest version from webhook |
| `homeassistant/pico/availability` | State | Device online/offline |

## Configuration

### config.py (Non-secret)

```python
# Device
DEVICE_NAME = "Raspberry Pi Pico 2W"
DEVICE_IDENTIFIER = "pico2w"

# Pins
DS18B20_PIN = 22
INTERNAL_TEMP_ADC_PIN = 4

# ACS37030 (current sensors)
ENABLE_ACS37030 = True
ACS37030_I2C_ADDRESS = 0x48
ACS37030_I2C_SCL_PIN = 5
ACS37030_I2C_SDA_PIN = 4
ACS37030_NUM_SENSORS = 5
ACS37030_PICO_ADC_PIN = 26
ENABLE_ACS37030_PICO_ADC = False

# Timing
SENSOR_UPDATE_INTERVAL_MS = 1000
TEMP_CONVERSION_TIME_MS = 750

# GitHub
GITHUB_OWNER = "exploreborders"
GITHUB_REPO = "explorePico"
```

### secrets.py (Private - NOT committed)

```python
# WiFi
WIFI_SSID = "YourNetwork"
WIFI_PASSWORD = "YourPassword"
WIFI_SSID_2 = "BackupNetwork"  # Optional
WIFI_PASSWORD_2 = "Password2"

# MQTT
MQTT_BROKER = "broker.example.com"
MQTT_PORT = 8883
MQTT_USER = "username"
MQTT_PASSWORD = "password"

# GitHub (optional, for private repos)
GITHUB_TOKEN = "ghp_xxx"
```

## Sensor Details

### DS18B20 Temperature

- **GPIO:** GP22 (configurable)
- **Protocol:** 1-Wire
- **Max Sensors:** ~10 on single bus
- **Conversion Time:** 750ms (12-bit)
- **Assignment:**
  - Index 0 → Room temperature
  - Index 1 → Water temperature
- **Auto-detection:** Sensors added/removed at runtime are detected

### ACS37030 Current (±20A)

- **Sensors 1-4:** ADS1115 I2C (channels A0-A3)
- **Sensor 5:** Pico ADC (GP26, optional)
- **Sensitivity:** 66 mV/A
- **Zero Point:** 1.65V (bidirectional)
- **Buffer:** Moving average (default 10 samples)

### Internal Temperature

- **Sensor:** RP2350 band-gap
- **ADC Pin:** ADC4
- **Formula:** `27 - (voltage - 0.706) / 0.001721`

## GitHub OTA Updates

### Requirements

1. Public repository (or GITHUB_TOKEN for private)
2. Releases with attached .py files
3. Version tag format: `1.2.3` or `v1.2.3`

### Files to Attach to Release

- main.py, app.py, config.py
- github_updater.py, blink.py, wifi_utils.py, updater_utils.py
- sensors/__init__.py, sensors/ds18b20.py, sensors/acs37030.py, sensors/ads1115.py

### LED Feedback Patterns

| Pattern | Meaning |
|---------|---------|
| "10" | WiFi connecting |
| "1010" | WiFi connected |
| "11" | Checking GitHub |
| "11011" | Update complete, rebooting |
| "111" | Error |


## Testing Checklist

- [x] WiFi connects (primary + backup network)
- [x] MQTT connects to broker (SSL/non-SSL)
- [x] DS18B20 sensors read correctly
- [x] ACS37030 current sensors read correctly (1-5)
- [x] Home Assistant discovers all entities
- [x] LED control works via MQTT
- [x] Auto-reconnect works after network loss
- [x] GitHub update check works
- [x] Update downloads and applies correctly
- [x] Rollback restores previous version
- [x] Update entity shows progress in HA

## Notes

### MicroPython Specifics

- Use `ujson` not `json`
- Use `time.ticks_ms()` not `time.time()`
- Use `time.ticks_diff()` for timing calculations
- Exception buffer: `micropython.alloc_emergency_exception_buf(200)`

### Hardware Constraints

- Watchdog max ~8388ms
- DS18B20 conversion: 750ms
- ADS1115 sample time: 150ms per channel
- MQTT keepalive: 30s

### Timing Constants

| Parameter | Value |
|-----------|-------|
| Sensor publish interval | 1000ms |
| DS18B20 conversion | 750ms |
| Sensor retry interval | 60000ms |
| MQTT keepalive | 30s |
| Reconnect delay | 5s (max 30s) |
| Rollback window | 2 seconds |
