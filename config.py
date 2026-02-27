"""
Configuration for Pico 2W MQTT Client

This module contains all configuration constants for the project.
Configuration is separated into groups:

MQTT Configuration:
    - MQTT_BROKER, MQTT_PORT, MQTT_USER, MQTT_PASSWORD: Broker connection
    - MQTT_SSL: Enable/disable SSL/TLS
    - TOPIC_*: MQTT topic definitions for Home Assistant

Device Configuration:
    - DEVICE_NAME, DEVICE_IDENTIFIER: Device identification
    - INTERNAL_TEMP_ADC_PIN: RP2350 internal temperature sensor

Sensor Configuration:
    - DS18B20_PIN: GPIO pin for DS18B20 sensors
    - ISNS20_CS_PIN, ISNS20_SPI_PORT: ISNS20 current sensor
    - ISNS20_SPI*_PINS: SPI pin definitions for ISNS20

Timing Configuration:
    - SENSOR_UPDATE_INTERVAL_MS: How often to read sensors
    - SENSOR_RETRY_INTERVAL_MS: Sensor reconnection retry interval
    - TEMP_CONVERSION_TIME_MS: DS18B20 conversion time
    - MQTT_DELAY_*: MQTT operation delays
    - ERROR_DELAY_*: Error handling delays

Update Configuration:
    - SD_SCK_PIN, SD_MOSI_PIN, SD_MISO_PIN, SD_CS_PIN: SD card pins
    - UPDATE_BUTTON_PIN: GPIO pin for rollback trigger
    - GITHUB_OWNER, GITHUB_REPO: GitHub repository for OTA updates

Secrets:
    WiFi and MQTT credentials are loaded from secrets.py.
    Copy config.py to secrets.py and fill in your credentials.
    Ensure secrets.py is in .gitignore to avoid committing credentials.
"""

# MQTT Configuration
MQTT_SSL = True  # Enable SSL/TLS

# Device Configuration
DEVICE_NAME = "Raspberry Pi Pico 2W"
DEVICE_IDENTIFIER = "pico2w"

# MQTT Topics
TOPIC_LED_COMMAND = "homeassistant/switch/pico/led/set"
TOPIC_LED_STATE = "homeassistant/switch/pico/led/state"
TOPIC_LED_CONFIG = "homeassistant/switch/pico/led/config"

TOPIC_TEMP_STATE = "homeassistant/sensor/pico/cpu_temp"
TOPIC_TEMP_CONFIG = "homeassistant/sensor/pico/cpu_temp/config"

TOPIC_ROOM_TEMP_STATE = "homeassistant/sensor/pico/room_temp"
TOPIC_ROOM_TEMP_CONFIG = "homeassistant/sensor/pico/room_temp/config"

TOPIC_WATER_TEMP_STATE = "homeassistant/sensor/pico/water_temp"
TOPIC_WATER_TEMP_CONFIG = "homeassistant/sensor/pico/water_temp/config"

TOPIC_CURRENT_STATE = "homeassistant/sensor/pico/current"
TOPIC_CURRENT_CONFIG = "homeassistant/sensor/pico/current/config"

# Device availability topic (for last-will and birth message)
TOPIC_AVAILABILITY = "homeassistant/sensor/pico/availability"

# DS18B20 Configuration
DS18B20_PIN = 22  # GPIO pin for DS18B20 temperature sensors (supports multiple)

# Internal Temperature Sensor
INTERNAL_TEMP_ADC_PIN = 4  # RP2350 internal temperature sensor (ADC4)

# ISNS20 Current Sensor Configuration
ENABLE_ISNS20 = False  # Set to False if ISNS20 sensor is not connected
ISNS20_CS_PIN = 8  # GPIO pin for ISNS20 chip select
ISNS20_SPI_PORT = 0  # SPI port 0 or 1

# ISNS20 SPI0 Pins (used when ISNS20_SPI_PORT = 0)
ISNS20_SPI0_SCK_PIN = 2
ISNS20_SPI0_MOSI_PIN = 3
ISNS20_SPI0_MISO_PIN = 4

# ISNS20 SPI1 Pins (used when ISNS20_SPI_PORT = 1)
ISNS20_SPI1_SCK_PIN = 10
ISNS20_SPI1_MOSI_PIN = 11
ISNS20_SPI1_MISO_PIN = 12

# Timing
SENSOR_UPDATE_INTERVAL_MS = 1000
RECONNECT_DELAY_S = 5
TEMP_CONVERSION_TIME_MS = 750  # DS18B20 conversion time
SENSOR_RETRY_INTERVAL_MS = 60000  # Retry failed sensor init every 60s

# MQTT Timing Delays
MQTT_DELAY_DISCOVERY = 0.2  # Between discovery publishes
MQTT_DELAY_CONNECT = 0.3  # After connect, before subscribe
MQTT_DELAY_SUBSCRIBE = 0.3  # After subscribe, before discovery
MQTT_DELAY_INITIAL_STATE = 0.2  # After discovery, before initial state
MQTT_LOOP_DELAY = 0.1  # Main loop iteration delay
ERROR_DELAY_SHORT = 1.0  # After minor error
ERROR_DELAY_LONG = 2.0  # After serious error/connection lost

# SD Card Updater Configuration
SD_SCK_PIN = 14
SD_MOSI_PIN = 15
SD_MISO_PIN = 12
SD_CS_PIN = 13
UPDATE_BUTTON_PIN = 10

# GitHub WiFi Updater Configuration
GITHUB_OWNER = "exploreborders"
GITHUB_REPO = "explorePico"

# Try to import from secrets.py, fallback to this file for development
try:
    from secrets import (
        WIFI_SSID,
        WIFI_PASSWORD,
        MQTT_BROKER,
        MQTT_PORT,
        MQTT_USER,
        MQTT_PASSWORD,
    )
except ImportError:
    raise ImportError(
        "secrets.py not found! Copy config.py to secrets.py "
        "and fill in your credentials, then add secrets.py to .gitignore"
    )


def validate_config() -> bool:
    """Validate configuration settings. Raises ValueError if invalid."""
    errors = []

    if not WIFI_SSID or not isinstance(WIFI_SSID, str):
        errors.append("WIFI_SSID must be a non-empty string")

    if not WIFI_PASSWORD or not isinstance(WIFI_PASSWORD, str):
        errors.append("WIFI_PASSWORD must be a non-empty string")

    if not MQTT_BROKER or not isinstance(MQTT_BROKER, str):
        errors.append("MQTT_BROKER must be a non-empty string")

    if not isinstance(MQTT_PORT, int) or MQTT_PORT < 1 or MQTT_PORT > 65535:
        errors.append("MQTT_PORT must be an integer between 1 and 65535")

    if not MQTT_USER or not isinstance(MQTT_USER, str):
        errors.append("MQTT_USER must be a non-empty string")

    if not MQTT_PASSWORD or not isinstance(MQTT_PASSWORD, str):
        errors.append("MQTT_PASSWORD must be a non-empty string")

    if not isinstance(DS18B20_PIN, int) or DS18B20_PIN < 0 or DS18B20_PIN > 28:
        errors.append("DS18B20_PIN must be 0-22 or 26-28 (23-25, 29 reserved)")

    if not isinstance(ISNS20_CS_PIN, int) or ISNS20_CS_PIN < 0 or ISNS20_CS_PIN > 28:
        errors.append("ISNS20_CS_PIN must be 0-22 or 26-28 (23-25, 29 reserved)")

    if ISNS20_SPI_PORT not in (0, 1):
        errors.append("ISNS20_SPI_PORT must be 0 or 1")

    if not isinstance(SD_SCK_PIN, int) or SD_SCK_PIN < 0 or SD_SCK_PIN > 28:
        errors.append("SD_SCK_PIN must be 0-22 or 26-28")

    if not isinstance(SD_MOSI_PIN, int) or SD_MOSI_PIN < 0 or SD_MOSI_PIN > 28:
        errors.append("SD_MOSI_PIN must be 0-22 or 26-28")

    if not isinstance(SD_MISO_PIN, int) or SD_MISO_PIN < 0 or SD_MISO_PIN > 28:
        errors.append("SD_MISO_PIN must be 0-22 or 26-28")

    if not isinstance(SD_CS_PIN, int) or SD_CS_PIN < 0 or SD_CS_PIN > 28:
        errors.append("SD_CS_PIN must be 0-22 or 26-28")

    if (
        not isinstance(UPDATE_BUTTON_PIN, int)
        or UPDATE_BUTTON_PIN < 0
        or UPDATE_BUTTON_PIN > 28
    ):
        errors.append("UPDATE_BUTTON_PIN must be 0-22 or 26-28")

    if errors:
        raise ValueError(
            "Config validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return True
