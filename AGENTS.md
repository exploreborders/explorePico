# AGENTS.md - Pico 2W MQTT Client

## Project Overview

MicroPython project for Raspberry Pi Pico 2W integrating with Home Assistant via MQTT. Reads DS18B20 temperature sensors and ACS37030 current sensors via ADS1115. Supports OTA firmware updates via GitHub.

**Tech Stack:** MicroPython, Raspberry Pi Pico 2W (RP2350), umqtt.simple, DS18B20, ACS37030, ADS1115

## Project Structure

```
secondTest/
├── main.py            # Entry point (runs on boot)
├── app.py            # Main application (MQTT client)
├── config.py         # Configuration (pins, MQTT topics, timing)
├── secrets.py        # WiFi/MQTT credentials (NOT committed)
├── wifi_utils.py     # Shared WiFi connection utilities
├── blink.py          # Shared LED blink utilities
├── updater_utils.py  # Shared backup/restore, version, logging
├── github_updater.py # GitHub OTA updater
└── sensors/
    ├── __init__.py
    ├── ds18b20.py   # DS18B20 driver + DS18B20Manager
    ├── acs37030.py  # ACS37030 current sensor driver
    └── ads1115.py   # ADS1115 I2C ADC driver
```

---

## Build/Deploy Commands

### Linting
```bash
pip install ruff
ruff check .              # Check all issues
ruff check . --fix       # Auto-fix
ruff check main.py        # Single file
```

### Upload to Pico (MicroPico)
```bash
micropico connect
%send main.py app.py config.py secrets.py
%send github_updater.py blink.py wifi_utils.py updater_utils.py
%send -r sensors/
```

### Run Application
```python
import main
main.main()
```

---

## Code Style Guidelines

### Imports (Order: stdlib → third-party → local)
```python
import time
from umqtt.simple import MQTTClient
import machine
import ujson

from blink import blink_pattern, led
from wifi_utils import scan_and_connect, is_connected
from updater_utils import log, set_logger, read_version

from config import (...)
from sensors import DS18B20, DS18B20Manager
```

### Formatting
- **Line length:** Max 100 characters
- **Indentation:** 4 spaces (no tabs)
- **Blank lines:** 2 between top-level definitions, 1 between functions
- **No trailing whitespace**

### Type Hints (Python 3.10+ union syntax)
```python
def read_temperature() -> float:
def read_sensor() -> float | None:
def log(tag: str, message: str | None = None) -> None:
```

### Naming Conventions
| Type | Convention | Example |
|------|------------|---------|
| Functions | snake_case | `connect_wifi()` |
| Variables | snake_case | `mqtt_client` |
| Constants | UPPER_SNAKE | `MQTT_BROKER` |
| Classes | PascalCase | `DS18B20Manager` |
| Private vars | _snake_case | `_last_values` |

### Error Handling
- Use try/except for I/O (network, MQTT, sensor reads)
- Never swallow exceptions silently
- Declare globals at function start with `global`

---

## Key Patterns

### Shared Logger
```python
# In app.py - set logger once at startup
set_logger(lambda tag, msg: print(f"[{tag}] {msg}"), "APP")

# Anywhere - use shared log function
from updater_utils import log
log("TAG", "message")      # With custom tag
log("message only")        # Uses default tag
```

### MQTT Publish-If-Changed
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

### Sensor Manager Pattern
```python
sensor = Manager(Sensor(PIN), "Name", retry_interval_ms)
sensor.set_logger(log)
data = sensor.read()
```

---

## Important Design Principles

### DRY (Don't Repeat Yourself)
- All configuration in `config.py`
- All logging via `log()` from `updater_utils.py`
- All LED control in `blink.py` (single Pin instance)
- All WiFi functions in `wifi_utils.py`

### Hardware Configuration
- GPIO pins in `config.py` (e.g., `DS18B20_PIN = 22`)
- ADC pins in `config.py` (e.g., `INTERNAL_TEMP_ADC_PIN = 4`)

---

## Important Notes

### secrets.py
- **NEVER commit to git** (already in .gitignore)
- Contains WiFi credentials, MQTT credentials, and GitHub token

### MicroPython Differences
- Use `ujson` not `json`
- Use `time.ticks_ms()` not `time.time()`
- Use `time.ticks_diff()` for timing

### Hardware Constraints
- Watchdog max ~8388ms
- GPIO 0-22, 26-28 available (23-25, 29 reserved)
- DS18B20: 750ms conversion time
- ACS37030: I2C via ADS1115 on GP4/GP5

### Sensor Assignment
- First DS18B20 = room temp (index 0)
- Second DS18B20 = water temp (index 1)
- ACS37030 sensors = current_1 to current_5
- Missing sensors show "unavailable"
