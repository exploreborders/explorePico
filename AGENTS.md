# AGENTS.md - Pico 2W MQTT Client

## Project Overview

MicroPython project for Raspberry Pi Pico 2W integrating with Home Assistant via MQTT. Reads DS18B20 temperature sensors (multiple on single GPIO) and Pmod ISNS20 current sensor.

**Tech Stack:** MicroPython, Raspberry Pi Pico 2W (RP2350), umqtt.simple, DS18B20, Pmod ISNS20

## Project Structure

```
secondTest/
├── main.py            # Main application (MQTT client)
├── app.py            # Entry point - handles updates before launching main
├── config.py         # Configuration (pins, MQTT topics, timing)
├── secrets.py        # WiFi/MQTT credentials (NOT committed)
├── wifi_utils.py     # Shared WiFi connection utilities
├── blink.py          # Shared LED blink utilities
├── updater_utils.py  # Shared backup/restore, version, logging
├── sd_updater.py     # SD card updater
├── github_updater.py # GitHub WiFi updater
├── sensors/
│   ├── __init__.py
│   ├── ds18b20.py   # DS18B20 driver + DS18B20Manager
│   └── isns20.py    # ISNS20 current sensor driver
└── .vscode/         # VS Code settings for Pico
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
%send app.py
%send sd_updater.py
%send github_updater.py
%send blink.py
%send wifi_utils.py
%send updater_utils.py
%send main.py
%send config.py
%send secrets.py
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
import ubinascii
import micropython

from blink import blink_pattern, led
from wifi_utils import connect, is_connected
from updater_utils import log, set_logger

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
log("message only")         # Uses default tag
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
# Create sensor with manager
sensor = Manager(Sensor(PIN), "Name", RETRY_INTERVAL_MS)
sensor.set_logger(log)

# Read sensor data
data = sensor.read()
```

---

## Important Design Principles

### DRY (Don't Repeat Yourself)
- All configuration in `config.py`
- All logging via `log()` from `updater_utils.py`
- All LED control in `blink.py` (single Pin instance)
- All WiFi functions in `wifi_utils.py`
- All backup/restore/version in `updater_utils.py`

### Hardware Configuration
- GPIO pins in `config.py` (e.g., `DS18B20_PIN = 22`)
- ADC pins in `config.py` (e.g., `INTERNAL_TEMP_ADC_PIN = 4`)
- Device info in `config.py` (`DEVICE_NAME`, `DEVICE_IDENTIFIER`)

---

## Important Notes

### secrets.py
- **NEVER commit to git** (already in .gitignore)

### MicroPython Differences
- Use `ujson` not `json`
- Use `time.ticks_ms()` not `time.time()`
- Use `time.ticks_diff()` for timing

### Hardware
- Watchdog max ~8388ms
- GPIO 0-22, 26-28 available (23-25, 29 reserved)
- DS18B20: 750ms conversion time
- ISNS20: SPI0 on GP2/3/4, CS on GP8

### Sensor Assignment
- First DS18B20 = room temp (index 0)
- Second DS18B20 = water temp (index 1)
- Missing sensors show "unavailable"

---

## Adding New Features

1. Add GPIO pin to `config.py`
2. Import in `main.py`: `from config import NEW_PIN`
3. Create sensor manager with `set_logger(log)`
4. Add MQTT topics to `config.py`
5. Add publish function and `publish_discovery()`
6. Add to main loop
