# Pico 2W MQTT Client with SD Card Updater

MicroPython project for Raspberry Pi Pico 2W that integrates with Home Assistant via MQTT. Reads DS18B20 temperature sensors and Pmod ISNS20 current sensor. Supports wireless code updates via SD card.

## Features

- **Temperature Sensing**: Two DS18B20 temperature sensors on single GPIO (room + water)
- **Current Sensing**: Pmod ISNS20 20A current sensor
- **Home Assistant Integration**: Automatic MQTT discovery for all sensors
- **LED Control**: Control Pico LED via MQTT
- **Internal Temperature**: RP2350 internal temperature sensor
- **Auto-Reconnect**: WiFi and MQTT with exponential backoff
- **Sensor Hot-Swap**: Automatic detection of connected/disconnected sensors
- **SD Card Updates**: Update code via SD card without computer connection
- **Rollback**: Restore previous version if update fails

## Hardware

- Raspberry Pi Pico 2W (RP2350)
- 2x DS18B20 temperature sensors (waterproof probes recommended)
- 1x Pmod ISNS20 20A current sensor
- 1x micro SD card module (SPI)
- 1x push button (for update trigger)
- 1x 4.7kΩ resistor (for DS18B20 data line pull-up)

### GPIO Configuration

| Sensor | GPIO | Notes |
|--------|------|-------|
| DS18B20 (both) | GP22 | 1-Wire bus, supports multiple sensors |
| ISNS20 CS | GP8 | SPI Chip Select |
| ISNS20 SCK | GP2 | SPI Clock |
| ISNS20 MOSI | GP3 | SPI Data Out |
| ISNS20 MISO | GP4 | SPI Data In |
| SD Card MOSI | GP15 | SPI Data Out |
| SD Card MISO | GP12 | SPI Data In |
| SD Card SCK | GP14 | SPI Clock |
| SD Card CS | GP13 | Chip Select |
| Update Button | GP10 | Pulled HIGH internally |

### DS18B20 Wiring (Daisy-Chained)

Connect both DS18B20 sensors to the same GPIO using a single pull-up resistor:

```
                    4.7kΩ
 Pico GP22 ────────┬───────┬─────── DQ (yellow/white)
                    │       │
                   GND    GND
                    │       │
                   VDD    VDD
                  (red)  (red)
                   
           3V3 ────────┴───────┘
```

All sensors share:
- **Data (DQ)**: GP22
- **VCC**: 3V3
- **GND**: GND

### SD Card Module Wiring

| SD Module | Pico Pin |
|-----------|----------|
| VCC | 3V3 |
| GND | GND |
| MOSI | GP15 |
| MISO | GP12 |
| SCK | GP14 |
| CS | GP13 |

### Update Button Wiring (for Rollback)

| Button | Pico Pin |
|--------|----------|
| One leg | GP10 |
| Other leg | GND |

The button is used for rollback (double-press). Update is automatic when SD card is inserted.

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
%send boot.py
%send sd_updater.py
%send blink.py
%send main.py
%send config.py
%send secrets.py
%send -r sensors/
```

Or using mpremote:
```bash
mpremote cp main.py :
mpremote cp config.py :
mpremote cp secrets.py :
mpremote cp boot.py :
mpremote cp sd_updater.py :
mpremote cp blink.py :
mpremote cp -r sensors/ :
```

### 4. Run

The Pico will automatically run `boot.py` on power-up, which then runs `main.py`.

## SD Card Code Updater

### Overview

The SD Card Updater automatically detects an SD card with valid update files at boot and updates the Pico's code. No computer connection needed!

### How It Works

| Boot Event | Action | Result |
|------------|--------|--------|
| Normal boot | No SD card | Runs main.py normally |
| Normal boot | SD card (no update) | Runs main.py normally |
| Update | SD card with valid files | Auto-updates and reboots |
| Rollback | Double press button | Restores previous version |

### LED Feedback Patterns

| Pattern | Meaning |
|---------|---------|
| No blink | Normal boot, no SD card or no update |
| **Update** | |
| "1" | Update found, starting |
| "10" | No update needed (same/older version) |
| "111" | ✅ Update successful! |
| "000" | ❌ Update failed |
| **Rollback** | |
| "010" | Rollback detected |
| "1010" | ✅ Rollback successful! |
| "000" | ❌ Rollback failed |
| "1" | No backup found |

### Updating Code

1. **Prepare SD Card:**
   Format the SD card as FAT32 and create this structure:
   ```
   / (SD card root)
   └── update/
       ├── version.txt    # Version number (e.g., "2.0")
       ├── main.py        # New main.py (optional)
       ├── config.py      # New config.py (optional)
       ├── secrets.py     # New secrets.py (optional)
       └── sensors/       # New sensor files (optional)
   ```

2. **Version Number:**
   - The version in `version.txt` must be **higher** than the current version
   - Current version is stored in `/.version` on the Pico
   - Example: if current is "1.0", use "2.0" or "1.1"

3. **Trigger Update:**
   - Power off the Pico
   - Insert the SD card with update files
   - Power on the Pico
   - Watch the LED for success/failure

4. **Verify:**
   - LED "111" = success, Pico will reboot with new code
   - LED "000" = failed, Pico will boot with old code

### Rolling Back

If something goes wrong, you can restore the previous version:

1. Power off the Pico
2. Hold the button on GP10
3. Press button **twice** within 2 seconds
4. Watch the LED for "1010" (success) or "000" (failed)

### Safety Features

- **Manual trigger**: Button must be pressed at boot
- **Version check**: Won't update if version is same or lower
- **Backup**: Creates backup before updating
- **Auto-rollback**: If update fails, automatically restores previous version

## MQTT Topics

### State Topics

| Topic | Description |
|-------|-------------|
| `homeassistant/sensor/pico/cpu_temp` | Internal temperature (°C) |
| `homeassistant/sensor/pico/room_temp` | Room temperature (°C) |
| `homeassistant/sensor/pico/water_temp` | Water temperature (°C) |
| `homeassistant/sensor/pico/current` | Current measurement (A) |
| `homeassistant/switch/pico/led` | LED state (ON/OFF) |

### Control Topics

| Topic | Payload | Description |
|-------|---------|-------------|
| `homeassistant/switch/pico/led/set` | `ON` / `OFF` | Control LED |

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
- Verify GPIO pin in config.py (GP22)
- Check Serial output for error messages
- Ensure sensors have unique ROM codes (DS18B20 has built-in unique IDs)

### MQTT Connection Failed
- Verify broker address and port
- Check SSL settings (port 8883 for TLS)
- Ensure firewall allows MQTT ports

### ISNS20 Reading Wrong
- Ensure correct SPI wiring (SCK, MISO, CS)
- Check 3.3V power connection
- Verify no jumpers for 120Hz bandwidth (recommended)

### Temperature Sensors Swap
- First sensor found = room temp
- Second sensor found = water temp
- Sensors are auto-assigned by discovery order

### SD Card Updater Issues
- Ensure SD card is formatted FAT32
- Check SD card wiring (MOSI, MISO, SCK, CS)
- Verify button is connected to GP10 and GND
- Ensure version.txt contains higher version than current

## Project Structure

```
secondTest/
├── boot.py              # Entry point with SD update check
├── sd_updater.py       # SD card code updater module
├── blink.py            # Shared LED blink utilities
├── main.py             # Main application
├── config.py           # Configuration
├── secrets.py          # WiFi/MQTT credentials
├── version.txt         # Current version reference
├── sensors/
│   ├── __init__.py
│   ├── ds18b20.py      # Temperature sensor driver
│   └── isns20.py       # Current sensor driver
└── .vscode/            # VS Code settings
```

## License

MIT
