"""
Configuration for Pico 2W MQTT Client

This module contains all configuration constants for the project.
Configuration is separated into groups:

MQTT Configuration:
    - MQTT_BROKER, MQTT_PORT, MQTT_USER, MQTT_PASSWORD: Broker connection
    - MQTT_SSL: Enable/disable SSL/TLS
    - TOPIC_*: MQTT topic definitions for Home Assistant

Sensor Configuration:
    - DS18B20_PIN: GPIO pin for DS18B20 sensors
    - INTERNAL_TEMP_ADC_PIN: RP2350 internal temperature sensor
    - ACS37030_I2C_*: ADS1115 I2C configuration for ACS37030 sensors
    - ACS37030_NUM_SENSORS: Number of ACS37030 sensors (max 5)

Timing Configuration:
    - SENSOR_UPDATE_INTERVAL_MS: How often to read sensors
    - SENSOR_RETRY_INTERVAL_MS: Sensor reconnection retry interval
    - TEMP_CONVERSION_TIME_MS: DS18B20 conversion time
    - MQTT_DELAY_*: MQTT operation delays
    - ERROR_DELAY_*: Error handling delays

Update Configuration:
    - UPDATE_BUTTON_PIN: GPIO pin for rollback trigger (double-press at boot)
    - GITHUB_OWNER, GITHUB_REPO: GitHub repository for OTA updates

Secrets:
    WiFi and MQTT credentials are loaded from secrets.py.
    Copy config.py to secrets.py and fill in your credentials.
    Ensure secrets.py is in .gitignore to avoid committing credentials.
"""

# MQTT Configuration
MQTT_SSL = True  # Enable SSL (port 8883 - works with LTE)

# MQTT Topics
TOPIC_LED_COMMAND = "homeassistant/pico/switch/led/set"
TOPIC_LED_STATE = "homeassistant/pico/switch/led/state"

TOPIC_TEMP_STATE = "homeassistant/pico/sensor/cpu_temp"

TOPIC_ROOM_TEMP_STATE = "homeassistant/pico/sensor/room_temp"

TOPIC_WATER_TEMP_STATE = "homeassistant/pico/sensor/water_temp"

# ACS37030 Current Sensors (5 sensors)
TOPIC_CURRENT_1_STATE = "homeassistant/pico/sensor/current_1"
TOPIC_CURRENT_2_STATE = "homeassistant/pico/sensor/current_2"
TOPIC_CURRENT_3_STATE = "homeassistant/pico/sensor/current_3"
TOPIC_CURRENT_4_STATE = "homeassistant/pico/sensor/current_4"
TOPIC_CURRENT_5_STATE = "homeassistant/pico/sensor/current_5"

# Current sensor offset topics (receive from HA input_number)
TOPIC_CURRENT_1_OFFSET = "homeassistant/pico/sensor/current_1/offset"
TOPIC_CURRENT_2_OFFSET = "homeassistant/pico/sensor/current_2/offset"
TOPIC_CURRENT_3_OFFSET = "homeassistant/pico/sensor/current_3/offset"
TOPIC_CURRENT_4_OFFSET = "homeassistant/pico/sensor/current_4/offset"
TOPIC_CURRENT_5_OFFSET = "homeassistant/pico/sensor/current_5/offset"

# Current sensor offset state topics (reply to HA)
TOPIC_CURRENT_1_OFFSET_STATE = "homeassistant/pico/sensor/current_1/offset_state"
TOPIC_CURRENT_2_OFFSET_STATE = "homeassistant/pico/sensor/current_2/offset_state"
TOPIC_CURRENT_3_OFFSET_STATE = "homeassistant/pico/sensor/current_3/offset_state"
TOPIC_CURRENT_4_OFFSET_STATE = "homeassistant/pico/sensor/current_4/offset_state"
TOPIC_CURRENT_5_OFFSET_STATE = "homeassistant/pico/sensor/current_5/offset_state"

# Device availability topic (for last-will and birth message)
TOPIC_AVAILABILITY = "homeassistant/pico/availability"

# Update Entity Topics (HA native update entity)
TOPIC_UPDATE_STATE = "homeassistant/pico/update/state"
TOPIC_UPDATE_CMD = "homeassistant/pico/update/cmd"
TOPIC_UPDATE_LATEST = "homeassistant/pico/update/latest_version"

# DS18B20 Configuration
DS18B20_PIN = 22  # GPIO pin for DS18B20 temperature sensors (supports multiple)

# Internal Temperature Sensor
INTERNAL_TEMP_ADC_PIN = 4  # RP2350 internal temperature sensor (ADC4)

# ACS37030 Current Sensor Configuration (via ADS1115 I2C)
ENABLE_ACS37030 = True  # Set to False if ACS37030 sensors not connected
ACS37030_I2C_ADDRESS = 0x48  # ADS1115 I2C address
ACS37030_I2C_SCL_PIN = 5  # I2C0 SCL (GP5)
ACS37030_I2C_SDA_PIN = 4  # I2C0 SDA (GP4)
ACS37030_I2C_ID = 0  # Use I2C0
ACS37030_SENSITIVITY = 0.066  # V/A for ±20A (66 mV/A version)
ACS37030_ZERO_POINT = 1.65  # V (zero current voltage)
ACS37030_ZERO_OFFSET = (
    0.00  # Calibration offset (adjust if not exactly 0A at no current)
)
ACS37030_NUM_SENSORS = 5  # Number of ACS37030 sensors (max 5)
ACS37030_PICO_ADC_PIN = 26  # GP26 for 5th sensor (ADC0)
ENABLE_ACS37030_PICO_ADC = True  # Set to True when 5th sensor is physically connected
ACS37030_BUFFER_SIZE = (
    10  # Moving average buffer size (higher = smoother but slower response)
)

# Timing
SENSOR_UPDATE_INTERVAL_MS = 1000
RECONNECT_DELAY_S = 5
TEMP_CONVERSION_TIME_MS = 750  # DS18B20 conversion time
SENSOR_RETRY_INTERVAL_MS = 60000  # Retry failed sensor init every 60s

# MQTT Timing Delays (increased for LTE/SSL stability)
MQTT_DELAY_DISCOVERY = 0.8  # Between discovery publishes
MQTT_DELAY_CONNECT = 2.0  # After connect, before subscribe
MQTT_DELAY_SUBSCRIBE = 1.0  # After subscribe, before discovery
MQTT_DELAY_INITIAL_STATE = 1.0  # After discovery, before initial state
MQTT_LOOP_DELAY = 0.1  # Main loop iteration delay
ERROR_DELAY_SHORT = 1.0  # After minor error
ERROR_DELAY_LONG = 3.0  # After serious error/connection lost

# GitHub WiFi Updater Configuration
GITHUB_OWNER = "exploreborders"
GITHUB_REPO = "explorePico"
GITHUB_UPDATES_ENABLED = False  # Enable/disable GitHub OTA updates

# -----------------------------------------------------------------------------
# LTE / SIM7600G-H Configuration
# -----------------------------------------------------------------------------
# Wiring: SIM7600 TXD→GP1, RXD→GP0, VIO→3V3, VBUS→5V
# See AGENTS.md for complete wiring diagram
LTE_ENABLED = True
LTE_UART_ID = 0
LTE_TX_PIN = 0  # GP0 → SIM7600 RXD (NOTE: TX/RX crossed!)
LTE_RX_PIN = 1  # GP1 → SIM7600 TXD
LTE_BAUD = 115200  # Default baud rate
LTE_APN = "internet"  # O2 APN
LTE_SIM_PIN = "5046"  # O2 SIM PIN

LTE_CONNECT_TIMEOUT_MS = 90000

# GPS Configuration
ENABLE_GPS = True
GPS_UPDATE_INTERVAL_MS = 5000  # 5 seconds (direct polling, no background thread)

# Signal & Network Update Intervals
SIGNAL_UPDATE_INTERVAL_MS = 10000  # 10 seconds
NETWORK_INFO_UPDATE_INTERVAL_MS = 300000

# Connection Priority (try first, fallback second)
PRIMARY_CONNECTION = "WIFI"
FALLBACK_CONNECTION = "LTE"

# -----------------------------------------------------------------------------
# LTE/GPS/Network MQTT Topics
# -----------------------------------------------------------------------------
TOPIC_CONNECTION_TYPE = "homeassistant/pico/sensor/connection_type"

TOPIC_SIGNAL_RSSI = "homeassistant/pico/sensor/signal_rssi"
TOPIC_SIGNAL_QUALITY = "homeassistant/pico/sensor/signal_quality"

TOPIC_NETWORK_OPERATOR = "homeassistant/pico/sensor/network_operator"
TOPIC_NETWORK_TYPE = "homeassistant/pico/sensor/network_type"

TOPIC_GPS_LATITUDE = "homeassistant/pico/sensor/gps_latitude"
TOPIC_GPS_LONGITUDE = "homeassistant/pico/sensor/gps_longitude"
TOPIC_GPS_ALTITUDE = "homeassistant/pico/sensor/gps_altitude"
TOPIC_GPS_SPEED = "homeassistant/pico/sensor/gps_speed"
TOPIC_GPS_SATELLITES = "homeassistant/pico/sensor/gps_satellites"
TOPIC_GPS_PDOP = "homeassistant/pico/sensor/gps_pdop_accuracy"
TOPIC_GPS_COURSE = "homeassistant/pico/sensor/gps_course"

TOPIC_GPS_FIX_STATUS = "homeassistant/pico/sensor/gps_fix_status"

TOPIC_GPS_INTERVAL_SET = "homeassistant/pico/gps/set_interval"

TOPIC_DEVICE_TRACKER = "homeassistant/device_tracker/pico2w/location"

# Try to import from secrets.py, fallback to this file for development
try:
    from secrets import (
        WIFI_SSID,
        WIFI_PASSWORD,
        WIFI_SSID_2,
        WIFI_PASSWORD_2,
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

    # Secondary WiFi is optional but if provided, must be valid
    if WIFI_SSID_2 is not None:
        if not isinstance(WIFI_SSID_2, str):
            errors.append("WIFI_SSID_2 must be a string")
        if WIFI_PASSWORD_2 is None or not isinstance(WIFI_PASSWORD_2, str):
            errors.append("WIFI_PASSWORD_2 must be provided if WIFI_SSID_2 is set")

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

    # Internal temp ADC pin (RP2350 ADC0-ADC4)
    if (
        not isinstance(INTERNAL_TEMP_ADC_PIN, int)
        or INTERNAL_TEMP_ADC_PIN < 0
        or INTERNAL_TEMP_ADC_PIN > 4
    ):
        errors.append("INTERNAL_TEMP_ADC_PIN must be 0-4 (RP2350 ADC pins)")

    # LTE UART ID
    if not isinstance(LTE_UART_ID, int) or LTE_UART_ID < 0 or LTE_UART_ID > 1:
        errors.append("LTE_UART_ID must be 0 or 1")

    # LTE UART pins
    if (
        not isinstance(LTE_TX_PIN, int)
        or LTE_TX_PIN < 0
        or LTE_TX_PIN > 28
        or LTE_TX_PIN in (23, 24, 25, 29)
    ):
        errors.append("LTE_TX_PIN must be 0-22 or 26-28 (23-25, 29 reserved)")

    if (
        not isinstance(LTE_RX_PIN, int)
        or LTE_RX_PIN < 0
        or LTE_RX_PIN > 28
        or LTE_RX_PIN in (23, 24, 25, 29)
    ):
        errors.append("LTE_RX_PIN must be 0-22 or 26-28 (23-25, 29 reserved)")

    if errors:
        raise ValueError(
            "Config validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return True
