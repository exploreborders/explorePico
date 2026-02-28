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
    - ACS37030_I2C_*: ADS1115 I2C configuration for ACS37030 sensors
    - ACS37030_NUM_SENSORS: Number of ACS37030 sensors (max 5)

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

# ACS37030 Current Sensors (5 sensors)
TOPIC_CURRENT_1_STATE = "homeassistant/sensor/pico/current_1"
TOPIC_CURRENT_1_CONFIG = "homeassistant/sensor/pico/current_1/config"
TOPIC_CURRENT_2_STATE = "homeassistant/sensor/pico/current_2"
TOPIC_CURRENT_2_CONFIG = "homeassistant/sensor/pico/current_2/config"
TOPIC_CURRENT_3_STATE = "homeassistant/sensor/pico/current_3"
TOPIC_CURRENT_3_CONFIG = "homeassistant/sensor/pico/current_3/config"
TOPIC_CURRENT_4_STATE = "homeassistant/sensor/pico/current_4"
TOPIC_CURRENT_4_CONFIG = "homeassistant/sensor/pico/current_4/config"
TOPIC_CURRENT_5_STATE = "homeassistant/sensor/pico/current_5"
TOPIC_CURRENT_5_CONFIG = "homeassistant/sensor/pico/current_5/config"

# Device availability topic (for last-will and birth message)
TOPIC_AVAILABILITY = "homeassistant/sensor/pico/availability"

# Update Button Topics
TOPIC_UPDATE_COMMAND = "homeassistant/button/pico/update/set"
TOPIC_UPDATE_STATE = "homeassistant/button/pico/update/state"
TOPIC_UPDATE_CONFIG = "homeassistant/button/pico/update/config"

# DS18B20 Configuration
DS18B20_PIN = 22  # GPIO pin for DS18B20 temperature sensors (supports multiple)

# Internal Temperature Sensor
INTERNAL_TEMP_ADC_PIN = 4  # RP2350 internal temperature sensor (ADC4)

# ACS37030 Current Sensor Configuration (via ADS1115 I2C)
ENABLE_ACS37030 = True  # Set to False if ACS37030 sensors not connected
ACS37030_I2C_ADDRESS = 0x48  # ADS1115 I2C address
ACS37030_I2C_SCL_PIN = 5  # I2C1 SCL (GP5)
ACS37030_I2C_SDA_PIN = 4  # I2C1 SDA (GP4)
ACS37030_SENSITIVITY = 0.066  # V/A for ±20A (66 mV/A version)
ACS37030_ZERO_POINT = 1.65  # V (zero current voltage)
ACS37030_NUM_SENSORS = 5  # Number of ACS37030 sensors (max 5)
ACS37030_PICO_ADC_PIN = 26  # GP26 for 5th sensor (ADC0)

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

    if (
        not isinstance(ACS37030_I2C_SCL_PIN, int)
        or ACS37030_I2C_SCL_PIN < 0
        or ACS37030_I2C_SCL_PIN > 28
    ):
        errors.append("ACS37030_I2C_SCL_PIN must be 0-22 or 26-28")

    if (
        not isinstance(ACS37030_I2C_SDA_PIN, int)
        or ACS37030_I2C_SDA_PIN < 0
        or ACS37030_I2C_SDA_PIN > 28
    ):
        errors.append("ACS37030_I2C_SDA_PIN must be 0-22 or 26-28")

    if (
        not isinstance(ACS37030_PICO_ADC_PIN, int)
        or ACS37030_PICO_ADC_PIN < 0
        or ACS37030_PICO_ADC_PIN > 28
    ):
        errors.append("ACS37030_PICO_ADC_PIN must be 0-22 or 26-28")

    if (
        not isinstance(ACS37030_NUM_SENSORS, int)
        or ACS37030_NUM_SENSORS < 1
        or ACS37030_NUM_SENSORS > 5
    ):
        errors.append("ACS37030_NUM_SENSORS must be 1-5")

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
