# AGENTS.md - Pico 2W MQTT Client

## Project Overview

This is a MicroPython project for Raspberry Pi Pico 2W that integrates with Home Assistant via MQTT. It reads temperature sensors (DS18B20) and publishes to MQTT topics for Home Assistant discovery.

**Tech Stack:**
- MicroPython (not standard Python)
- Raspberry Pi Pico 2W (RP2350)
- umqtt.simple for MQTT
- DS18B20 one-wire temperature sensors

---

## Project Structure

```
secondTest/
├── main.py           # Main application (~420 lines)
├── config.py         # Configuration settings
├── secrets.py        # WiFi/MQTT credentials (NOT committed)
├── sensors/
│   ├── __init__.py
│   └── ds18b20.py   # DS18B20 driver + DS18B20Manager
└── .vscode/         # VS Code settings for Pico
```

---

## Build/Deploy Commands

### Upload to Pico

**Using MicroPico (recommended):**
```bash
# Connect Pico via USB and run:
micropico connect
# Then in micropico console:
%send main.py
%send config.py
%send secrets.py
%send -r sensors/
```

**Using rshell:**
```bash
rshell -p /dev/tty.usbmodem* repl
cp main.py /pyboard/
cp config.py /pyboard/
cp secrets.py /pyboard/
cp -r sensors /pyboard/
```

**Using ampy:**
```bash
ampy --port /dev/tty.usbmodem* put main.py
ampy --port /dev/tty.usbmodem* put config.py
ampy --port /dev/tty.usbmodem* put secrets.py
ampy --port /dev/tty.usbmodem* put sensors/
```

### Run Main Application

```python
# In Pico REPL
import main
main.main()
```

---

## Linting & Code Quality

### Ruff (Local Python Linting)

```bash
# Install ruff
pip install ruff

# Check for issues
ruff check .

# Auto-fix
ruff check . --fix
```

**Note:** LSP errors about MicroPython imports (machine, network, umqtt) are false positives - these libraries are only available on the Pico, not locally.

### MicroPython Compatibility

To check MicroPython syntax locally:
```bash
# Using rpython (if installed)
rpython -m pycparser file.py

# Or just upload and check for SyntaxError
```

---

## Code Style Guidelines

### Imports

**Order:**
1. Standard library (network, time, etc.)
2. Third-party (umqtt.simple, machine, etc.)
3. Local project (config, sensors)

**Example:**
```python
import network
import time
from umqtt.simple import MQTTClient
import machine
import ujson
import ubinascii
import micropython

from config import (...)
from sensors import DS18B20, DS18B20Manager
```

### Formatting

- **Line length:** Max 100 characters (soft limit)
- **Indentation:** 4 spaces (no tabs)
- **Blank lines:** 2 between top-level definitions, 1 between functions
- **No trailing whitespace**

### Type Hints

Use Python 3.10+ union syntax (compatible with MicroPython):
```python
# Good
def read_temperature() -> float:
def read_sensor() -> float | None:
def process(data: dict) -> bool:

# Avoid (older syntax)
def read_sensor() -> Optional[float]:
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Functions | snake_case | `connect_wifi()` |
| Variables | snake_case | `mqtt_client` |
| Constants | UPPER_SNAKE | `MQTT_BROKER` |
| Classes | PascalCase | `DS18B20Manager` |
| Private vars | _snake_case | `_last_mqtt_values` |

### Function Guidelines

- **Single responsibility:** Each function does one thing
- **Max length:** ~40 lines (extract if longer)
- **Docstrings:** Use """ for public APIs
- **Early returns:** Prefer early returns over deeply nested conditionals

**Example:**
```python
def read_temperature() -> float:
    """Read internal temperature sensor (RP2350)."""
    reading = temp_sensor.read_u16()
    voltage = reading * 3.3 / 65535
    temp_c = 27 - (voltage - 0.706) / 0.001721
    return round(temp_c, 1)
```

### Error Handling

- **Use try/except for I/O operations:** Network, MQTT, sensor reads
- **Log errors:** Use the `log()` function with appropriate tag
- **Don't swallow exceptions silently:** At minimum, log the error

**Example:**
```python
def on_message(topic: bytes, msg: bytes) -> None:
    """Handle incoming MQTT messages."""
    global led_state
    try:
        topic_str = topic.decode()
        msg_str = msg.decode().strip().upper()
        log("MSG", f"{topic_str} = {msg_str}")
        if topic_str == TOPIC_LED_COMMAND:
            if msg_str == "ON":
                led.on()
                led_state = True
            elif msg_str == "OFF":
                led.off()
                led_state = False
    except Exception as e:
        log("ERROR", f"Message handling failed: {e}")
```

### Global Variables

Minimise globals. If needed, declare with `global` at function start:
```python
mqtt_client = None
led_state = False
_last_mqtt_values = {}

def some_function():
    global mqtt_client
    mqtt_client = create_client()
```

---

## Key Patterns

### MQTT Publish-If-Changed

Use `mqtt_publish()` for state topics - only publishes when value changes:
```python
def mqtt_publish(topic: str, value: str, retain: bool = True) -> bool:
    """Publish to MQTT only if value changed."""
    global _last_mqtt_values
    key = (topic, retain)
    if _last_mqtt_values.get(key) != value:
        mqtt_client.publish(topic, value, retain=retain)
        _last_mqtt_values[key] = value
        return True
    return False
```

### Sensor Manager Pattern

Use `DS18B20Manager` class for sensor handling:
- Auto-initialization
- Retry logic with configurable intervals
- Hot-swap detection
- Tracks connection state

### Reconnection with Backoff

For WiFi/MQTT:
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

---

## Testing

**No formal tests exist yet.**

To add tests, consider:
- Use `pytest` with `pytest-mock` for local testing
- Mock `machine`, `network`, `umqtt` imports
- Test sensor manager logic independently

---

## Adding New Features

### Adding a New Sensor

1. Add GPIO pin to `config.py`
2. Create sensor instance in `main.py`:
   ```python
   new_sensor = DS18B20Manager(DS18B20(NEW_PIN), "SensorName", SENSOR_RETRY_INTERVAL_MS)
   new_sensor.set_logger(log)
   ```
3. Add MQTT topics (TOPIC_X_STATE, TOPIC_X_CONFIG)
4. Add config getter function
5. Add publish function
6. Add to `publish_discovery()` and temperature publish loop
7. Use `mqtt_publish()` for state updates

### Adding MQTT Topic

1. Define topic constants at top of file
2. Add to discovery config if HA entity
3. Use `mqtt_publish(topic, value)` to publish

---

## Important Notes

### secrets.py

- **NEVER commit secrets.py to git**
- Already in .gitignore
- Copy config template and fill credentials

### MicroPython Differences

- No `math` module (use `u math`)
- No `json` module (use `ujson`)
- No `typing` module in older MicroPython
- Use `time.ticks_ms()` for timing, not `time.time()`
- MicroPython-specific: `machine.reset()`, `machine.unique_id()`

### Hardware Considerations

- Watchdog max ~8388ms (don't set higher)
- GPIO pins: 0-21 available, some reserved
- OneWire sensors share data pin (can chain multiple)
- 750ms conversion time for DS18B20 (non-blocking pattern recommended)

---

## VS Code Setup

The `.vscode/` folder contains Pico-specific settings. Install:
- MicroPico extension for VS Code
- Or use PyMakr extension

---

## Troubleshooting

**"Import could not be resolved"** - False positive for MicroPython libraries (machine, network, umqtt)

**Sensor not found** - Check wiring:
- Data pin needs 4.7kΩ pull-up resistor
- Correct GPIO pin in config
- Polarity correct (GND, VCC, Data)

**MQTT connection issues**:
- Check broker address/port
- Verify SSL settings match broker
- Check firewall allows port 8883 (SSL) or 1883 (plain)
