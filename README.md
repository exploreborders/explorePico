# Pico 2W MQTT Client

MicroPython project for Raspberry Pi Pico 2W that integrates with Home Assistant via MQTT. Reads DS18B20 temperature sensors and Pmod ISNS20 current sensor.

## Features

- **Temperature Sensing**: Two DS18B20 temperature sensors (room + water)
- **Current Sensing**: Pmod ISNS20 20A current sensor
- **Home Assistant Integration**: Automatic MQTT discovery for all sensors
- **LED Control**: Control Pico LED via MQTT
- **Internal Temperature**: RP2350 internal temperature sensor
- **Auto-Reconnect**: WiFi and MQTT with exponential backoff
- **Sensor Hot-Swap**: Automatic detection of connected/disconnected sensors

## Hardware

- Raspberry Pi Pico 2W (RP2350)
- 2x DS18B20 temperature sensors
- 1x Pmod ISNS20 20A current sensor

### GPIO Configuration

| Sensor | GPIO | Notes |
|--------|------|-------|
| DS18B20 (Room) | GP22 | Temperature |
| DS18B20 (Water) | GP21 | Temperature |
| ISNS20 CS | GP8 | SPI Chip Select |
| ISNS20 SCK | GP2 | SPI Clock |
| ISNS20 MISO | GP4 | SPI Data |

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
%send config.py
%send secrets.py
%send -r sensors/
```

Or using ampy:
```bash
ampy --port /dev/tty.usbmodem* put main.py
ampy --port /dev/tty.usbmodem* put config.py
ampy --port /dev/tty.usbmodem* put secrets.py
ampy --port /dev/tty.usbmodem* put sensors/
```

### 4. Run

```python
# In Pico REPL
import main
main.main()
```

## MQTT Topics

### State Topics

| Topic | Description |
|-------|-------------|
| `pico/temperature` | Internal temperature (°C) |
| `pico/room_temp` | Room temperature (°C) |
| `pico/water_temp` | Water temperature (°C) |
| `pico/current` | Current measurement (A) |
| `pico/led/state` | LED state (ON/OFF) |

### Control Topics

| Topic | Payload | Description |
|-------|---------|-------------|
| `pico/led/set` | `ON` / `OFF` | Control LED |

## Home Assistant

The device is automatically discovered via MQTT discovery. After running, you should see:

- `sensor.pico_temperature` - Internal temperature
- `sensor.pico_room_temperature` - Room temperature
- `sensor.pico_water_temperature` - Water temperature
- `sensor.pico_current` - Current measurement
- `switch.pico_led` - LED control

## Troubleshooting

### Sensor Not Found
- Check wiring and pull-up resistor (4.7kΩ for DS18B20)
- Verify GPIO pins in config.py
- Check Serial output for error messages

### MQTT Connection Failed
- Verify broker address and port
- Check SSL settings (port 8883 for TLS)
- Ensure firewall allows MQTT ports

### ISNS20 Reading Wrong
- Ensure correct SPI wiring (SCK, MISO, CS)
- Check 3.3V power connection
- Verify no jumpers for 120Hz bandwidth (recommended)

## Project Structure

```
secondTest/
├── main.py           # Main application
├── config.py        # Configuration
├── secrets.py       # WiFi/MQTT credentials
├── sensors/
│   ├── __init__.py
│   ├── ds18b20.py  # Temperature sensor driver
│   └── isns20.py   # Current sensor driver
└── .vscode/        # VS Code settings
```

## License

MIT
