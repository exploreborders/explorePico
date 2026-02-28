# Pico 2W MQTT Client with SD Card & GitHub Updater

MicroPython project for Raspberry Pi Pico 2W that integrates with Home Assistant via MQTT. Reads DS18B20 temperature sensors and ACS37030 current sensors. Supports wireless code updates via SD card or GitHub.

## Features

- **Temperature Sensing**: Two DS18B20 temperature sensors on single GPIO (room + water)
- **Current Sensing**: Up to 5x ACS37030LLZATR-020B3 (±20A) current sensors via ADS1115 I2C
- **Home Assistant Integration**: Automatic MQTT discovery for all sensors
- **LED Control**: Control Pico LED via MQTT
- **Internal Temperature**: RP2350 internal temperature sensor
- **Auto-Reconnect**: WiFi and MQTT with exponential backoff
- **Sensor Hot-Swap**: Automatic detection of connected/disconnected sensors
- **SD Card Updates**: Update code via SD card
- **GitHub WiFi Updates**: Auto-update from GitHub releases
- **Rollback**: Restore previous version if update fails

## Hardware

- Raspberry Pi Pico 2W (RP2350)
- 2x DS18B20 temperature sensors (waterproof probes recommended)
- 5x ACS37030LLZATR-020B3 (±20A) current sensors
- 1x ADS1115 4-channel I2C ADC
- 1x micro SD card module (SPI)
- 1x push button (for update trigger)
- 1x 4.7kΩ resistor (for DS18B20 data line pull-up)

### GPIO Configuration

| Sensor | GPIO | Notes |
|--------|------|-------|
| DS18B20 (both) | GP22 | 1-Wire bus, supports multiple sensors |
| ADS1115 SCL | GP5 | I2C1 Clock |
| ADS1115 SDA | GP4 | I2C1 Data |
| ACS37030 #5 | GP26 | Pico ADC for 5th current sensor |
| SD Card MOSI | GP15 | SPI Data Out |
| SD Card MISO | GP12 | SPI Data In |
| SD Card SCK | GP14 | SPI Clock |
| SD Card CS | GP13 | Chip Select |
| Update Button | GP10 | Pulled HIGH internally |

### DS18B20 Wiring (Daisy-Chained)

Connect both DS18B20 sensors to the same GPIO using a single pull-up resistor:

```
Pico GP22 ────────[4.7kΩ]─────── VCC (3.3V)
                  │
        ┌─────────┴─────────┐
        │                   │
       DQ                  DQ
    Sensor 1            Sensor 2
    (red) VCC          (red) VCC
    (black) GND        (black) GND
```

All sensors share:
- **Data (DQ)**: GP22
- **VCC**: 3V3
- **GND**: GND

### ACS37030 Current Sensor Wiring (via ADS1115)

The project supports up to 5 ACS37030LLZATR-020B3 (±20A) current sensors:
- 4 sensors via ADS1115 I2C ADC (channels A0-A3)
- 1 sensor via Pico's built-in ADC (GP26)

#### ADS1115 Wiring

| ADS1115 | Pico Pin |
|---------|----------|
| VDD | 3V3 |
| GND | GND |
| SCL | GP5 (I2C1 SCL) |
| SDA | GP4 (I2C1 SDA) |
| A0 | ACS37030 #1 VOUT |
| A1 | ACS37030 #2 VOUT |
| A2 | ACS37030 #3 VOUT |
| A3 | ACS37030 #4 VOUT |

#### ACS37030 #5 Wiring (Pico ADC)

| ACS37030 #5 | Pico Pin |
|-------------|----------|
| VDD | 3V3 |
| GND | GND |
| VOUT | GP26 (ADC0) |

#### ACS37030 Pinout

Each ACS37030 has these pins:
| Pin | Function |
|-----|----------|
| VDD | 3.3V |
| GND | Ground |
| VOUT | Analog output (0.33V at -20A, 1.65V at 0A, 2.97V at +20A) |
| VREF | Reference (optional) |

The current path (IP+/IP-) is used to pass the wire to measure current.

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

The button is checked during boot (after WiFi connects). Double-press within 2 seconds to trigger rollback.

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

Or using mpremote:
```bash
mpremote cp app.py :
mpremote cp sd_updater.py :
mpremote cp github_updater.py :
mpremote cp blink.py :
mpremote cp wifi_utils.py :
mpremote cp updater_utils.py :
mpremote cp main.py :
mpremote cp config.py :
mpremote cp secrets.py :
mpremote cp -r sensors/ :
```

### 4. Run

The Pico will automatically run `app.py` (or `boot.py` if renamed) on power-up, which then runs `main.py`.

> Note: For development, use `app.py` to avoid auto-execution. Rename to `boot.py` for production auto-start.

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
| **Boot Sequence** | |
| "10" | WiFi/MQTT Connecting |
| "1010" | WiFi/MQTT Connected (normal boot) |
| **Update/Rollback** | |
| "11" | Checking for updates |
| "11011" | ✅ Update/Rollback successful! |
| "111" | ❌ Failed (or no backup found) |

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
   - LED "11011" = success, Pico will reboot with new code
   - LED "111" = failed, Pico will boot with old code

### Rolling Back

If something goes wrong, you can restore the previous version:

1. Power on the Pico normally
2. Wait for boot sequence (WiFi connects)
3. Press button **twice** within 2 seconds
4. Watch the LED for "11011" (success) or "111" (failed)

### Safety Features

- **Manual trigger**: Button must be pressed at boot
- **Version check**: Won't update if version is same or lower
- **Backup**: Creates backup before updating
- **Auto-rollback**: If update fails, automatically restores previous version

## GitHub WiFi Updater

### Overview

The Pico can automatically check GitHub for new releases and update itself over WiFi. No computer or SD card needed!

### How It Works

```
Boot
    │
    ├─ GitHub Check (priority)
    │     │
    │     └─ Newer release? → Download → Write → Reboot
    │
    ├─ SD Card (fallback)
    │     │
    │     └─ Newer version? → Download → Write → Reboot
    │
    └─ Continue to main.py
```

### LED Feedback Patterns

| Pattern | Meaning |
|---------|---------|
| "10" | WiFi Connecting |
| "1010" | WiFi Connected (normal) |
| "111" | Failed |
| "11" | Checking GitHub |
| "11011" | Update complete, rebooting |

### Setup

1. **Make repo public**
2. **Create GitHub releases** with version tags (e.g., v1.7)
3. **Attach files** to release:
   - main.py
   - config.py
   - app.py (or boot.py if renamed)
   - blink.py
   - wifi_utils.py
   - updater_utils.py
   - sd_updater.py
   - github_updater.py
   - sensors/__init__.py
   - sensors/ds18b20.py
   - sensors/isns20.py

### Creating a GitHub Release

1. Go to your repo: https://github.com/exploreborders/explorePico
2. Click **Create a new release**
3. Tag version: `v1.7` (must start with v)
4. Release title: `v1.7`
5. Attach files by uploading them
6. Click **Publish release**

### Configuration

Edit `config.py` to set your GitHub repo:

```python
GITHUB_OWNER = "exploreborders"
GITHUB_REPO = "explorePico"
```

### Update Flow

1. Pico connects to WiFi
2. Checks GitHub API for latest release
3. Compares version with current
4. If newer: downloads files from release
5. Creates backup
6. Writes new files to flash
7. Reboots

### Safety Features

- Version comparison (won't downgrade)
- Backup before update
- Auto-rollback on failure
- SD card as fallback

### Notes

- Repository must be **public** (or use GitHub token)
- Files must be attached to the release
- Version format: `v1.x.x` (e.g., v1.7)

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

### ISNS20 Reading Wrong (Deprecated)
- This sensor is no longer supported. Use ACS37030 instead.

### ACS37030 Reading Wrong
- Verify ADS1115 I2C wiring (SCL=GP5, SDA=GP4)
- Check 3.3V power to both ADS1115 and ACS37030
- Verify ACS37030 sensitivity (66 mV/A for ±20A version)
- Zero current should read ~1.65V on VOUT

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
├── app.py             # Entry point with GitHub & SD update check
├── github_updater.py   # GitHub WiFi updater
├── sd_updater.py       # SD card updater
├── blink.py            # Shared LED blink utilities
├── wifi_utils.py       # Shared WiFi connection utilities
├── updater_utils.py    # Shared backup/restore, version, logging
├── main.py             # Main application
├── config.py           # Configuration
├── secrets.py          # WiFi/MQTT credentials
├── version.txt         # Current version reference
├── sensors/
│   ├── __init__.py
│   ├── ds18b20.py      # DS18B20 temperature sensor driver
│   ├── ads1115.py      # ADS1115 I2C ADC driver
│   └── acs37030.py     # ACS37030 current sensor driver
└── .vscode/            # VS Code settings
```

## License

MIT
