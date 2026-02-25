# AGENTS.md - Pico 2W MQTT Client

## Project Overview

MicroPython project for Raspberry Pi Pico 2W integrating with Home Assistant via MQTT. Reads DS18B20 temperature sensors (multiple on single GPIO) and Pmod ISNS20 current sensor.

**Tech Stack:** MicroPython, Raspberry Pi Pico 2W (RP2350), umqtt.simple, DS18B20, Pmod ISNS20

## Project Structure

```
secondTest/
├── main.py           # Main application (MQTT client)
├── boot.py           # Entry point - handles updates before launching main
├── config.py         # Configuration settings (all hardware pins, MQTT topics, timing)
├── secrets.py        # WiFi/MQTT credentials (NOT committed - in .gitignore)
├── wifi_utils.py     # Shared WiFi connection utilities
├── blink.py         # Shared LED blink utilities
├── updater_utils.py # Shared backup/restore, version, logging utilities
├── sd_updater.py    # SD card updater
├── github_updater.py# GitHub WiFi updater
├── sensors/
│   ├── __init__.py
│   ├── ds18b20.py   # DS18B20 driver + DS18B20Manager
│   └── isns20.py    # ISNS20 current sensor driver
└── .vscode/         # VS Code settings for Pico
```

---

## Build/Deploy Commands

### Upload to Pico (MicroPico)
```bash
micropico connect
%send main.py
%send config.py
%send secrets.py
%send -r sensors/
```

### Linting
```bash
pip install ruff
ruff check .           # Check all issues
ruff check . --fix     # Auto-fix
ruff check main.py     # Single file
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
def read_all_sensors() -> list[float | None]:
```

### Naming Conventions
| Type | Convention | Example |
|------|------------|---------|
| Functions | snake_case | `connect_wifi()` |
| Variables | snake_case | `mqtt_client` |
| Constants | UPPER_SNAKE | `MQTT_BROKER` |
| Classes | PascalCase | `DS18B20Manager` |
| Private vars | _snake_case | `_last_values` |

### Error Handling & Logging
- Use try/except for I/O (network, MQTT, sensor reads)
- Always use the shared `log()` function from `updater_utils`
- Log format: `log("TAG", "message")` or `log("message")` (uses default tag)
- Never swallow exceptions silently
- Never commit secrets/keys to the repository

---

## Key Patterns

### Shared Logger
```python
# In boot.py - set logger once at startup
set_logger(lambda tag, msg: print(f"[{tag}] {msg}"), "BOOT")

# Anywhere - use shared log function
from updater_utils import log
log("TAG", "message")
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

### Sensor Manager & Reconnection
Use `*Manager` classes for sensor handling with auto-init, retry logic, hot-swap detection.

```python
reconnect_count = 0
while True:
    if not connect():
        reconnect_count += 1
        delay = min(RECONNECT_DELAY_S * reconnect_count, 30)
        time.sleep(delay)
        if reconnect_count > 5:
            reconnect_count = 0
        continue
    reconnect_count = 0
```

### Multiple DS18B20 Sensors
```python
temps = temp_sensors.read(TEMP_CONVERSION_TIME_MS)
if temps and len(temps) > 0:
    room_temp = temps[0]   # First sensor found
    water_temp = temps[1] if len(temps) > 1 else None
```

---

## Important Design Principles

### DRY (Don't Repeat Yourself)
- All configuration goes in `config.py`
- All logging uses shared `log()` from `updater_utils.py`
- All LED control in `blink.py` (single Pin instance at module level)
- All WiFi functions in `wifi_utils.py`
- All backup/restore/version logic in `updater_utils.py`

### Hardware Configuration
- GPIO pins defined in `config.py` (e.g., `DS18B20_PIN = 22`)
- ADC pins defined in `config.py` (e.g., `INTERNAL_TEMP_ADC_PIN = 4`)
- Device info in `config.py` (`DEVICE_NAME`, `DEVICE_IDENTIFIER`)

### Config Validation
Runtime config validation via `validate_config()` in `config.py`:
- Validates WiFi/MQTT credentials are non-empty strings
- Validates GPIO pins in valid range (0-22, 26-28)
- Validates SPI port is 0 or 1
- Raises `ValueError` with detailed messages on validation failure

---

## Important Notes

### secrets.py
- **NEVER commit to git** (already in .gitignore)

### MicroPython Differences
- Use `ujson` not `json`
- Use `time.ticks_ms()` not `time.time()`
- Use `time.ticks_diff()` for timing calculations

### Hardware
- Watchdog max ~8388ms
- GPIO 0-22, 26-28 available (23-25, 29 reserved)
- DS18B20: 750ms conversion time, supports multiple sensors on single GPIO
- ISNS20: SPI0 on GP2/3/4, CS on GP8

### Temperature Sensors Assignment
- Multiple DS18B20 sensors on same GPIO are auto-assigned by discovery order
- First sensor found = room temperature (index 0)
- Second sensor found = water temperature (index 1)
- If only one sensor connected, water_temp shows "unavailable"

---

## Adding New Features

1. Add GPIO pin to `config.py`
2. Create sensor manager in `main.py`:
   ```python
   new_sensor = Manager(Sensor(PIN), "Name", RETRY_INTERVAL_MS)
   new_sensor.set_logger(log)
   ```
3. Add MQTT topics (TOPIC_X_STATE, TOPIC_X_CONFIG)
4. Add getter function and publish function
5. Add to `publish_discovery()` and main loop
