# AGENTS.md - Pico 2W MQTT Client

## Project Overview

MicroPython project for Raspberry Pi Pico 2W integrating with Home Assistant via MQTT. Reads DS18B20 temperature sensors and Pmod ISNS20 current sensor.

**Tech Stack:** MicroPython, Raspberry Pi Pico 2W (RP2350), umqtt.simple, DS18B20, Pmod ISNS20

## Project Structure

```
secondTest/
├── main.py           # Main application
├── config.py         # Configuration settings
├── secrets.py        # WiFi/MQTT credentials (NOT committed)
├── sensors/
│   ├── __init__.py
│   ├── ds18b20.py   # DS18B20 driver + DS18B20Manager
│   └── isns20.py    # ISNS20 current sensor driver
└── .vscode/         # VS Code settings for Pico
```

## Build/Deploy Commands

### Upload to Pico (MicroPico)
```bash
micropico connect
%send main.py
%send config.py
%send secrets.py
%send -r sensors/
```

### Linting & Code Quality
```bash
# Install ruff
pip install ruff

# Check issues
ruff check .

# Auto-fix
ruff check . --fix
```

### Run Application
```python
# In Pico REPL
import main
main.main()
```

**Note:** LSP errors about MicroPython imports (machine, network, umqtt) are false positives - these libraries only work on the Pico.

## Code Style Guidelines

### Imports (Order: stdlib → third-party → local)
```python
import network
import time
from umqtt.simple import MQTTClient
import machine
import ujson
import ubinascii

from config import (...)
from sensors import DS18B20, DS18B20Manager, ISNS20, ISNS20Manager
```

### Formatting
- **Line length:** Max 100 characters
- **Indentation:** 4 spaces (no tabs)
- **Blank lines:** 2 between top-level definitions, 1 between functions
- **No trailing whitespace**

### Type Hints (Python 3.10+ union syntax)
```python
# Good
def read_temperature() -> float:
def read_sensor() -> float | None:

# Avoid
def read_sensor() -> Optional[float]:
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
- Log errors with `log()` function
- Never swallow exceptions silently

```python
def on_message(topic: bytes, msg: bytes) -> None:
    try:
        topic_str = topic.decode()
        msg_str = msg.decode().strip().upper()
    except Exception as e:
        log("ERROR", f"Message handling failed: {e}")
```

### Global Variables
Declare with `global` at function start:
```python
mqtt_client = None

def some_function():
    global mqtt_client
    mqtt_client = create_client()
```

## Key Patterns

### MQTT Publish-If-Changed
```python
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
Use `*Manager` classes for sensor handling with auto-init, retry logic, hot-swap detection.

### Reconnection with Backoff
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

## Adding New Features

### Adding a New Sensor
1. Add GPIO pin to `config.py`
2. Create sensor in `main.py`:
   ```python
   new_sensor = Manager(Sensor(PIN), "Name", RETRY_INTERVAL_MS)
   new_sensor.set_logger(log)
   ```
3. Add MQTT topics (TOPIC_X_STATE, TOPIC_X_CONFIG)
4. Add getter function and publish function
5. Add to `publish_discovery()` and main loop

## Important Notes

### secrets.py
- **NEVER commit to git** (already in .gitignore)

### MicroPython Differences
- Use `ujson` not `json`
- Use `time.ticks_ms()` not `time.time()`
- No `math` module (use `u math`)

### Hardware
- Watchdog max ~8388ms
- GPIO 0-21 available
- DS18B20: 750ms conversion time (non-blocking)
- ISNS20: SPI0 on GP2/3/4, CS on GP8
