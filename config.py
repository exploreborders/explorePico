"""
Configuration for Pico 2W MQTT Client
"""

# MQTT Configuration
MQTT_SSL = True  # Enable SSL/TLS

# DS18B20 Configuration
DS18B20_PIN = 22  # GPIO pin for DS18B20 temperature sensors (supports multiple)

# ISNS20 Current Sensor Configuration
ISNS20_CS_PIN = 8  # GPIO pin for ISNS20 chip select
ISNS20_SPI_PORT = 0  # SPI port 0 (SCK=GP2, MOSI=GP3, MISO=GP4)

# Timing
TEMP_UPDATE_INTERVAL_MS = 1000
RECONNECT_DELAY_S = 5
TEMP_CONVERSION_TIME_MS = 750  # DS18B20 conversion time
SENSOR_RETRY_INTERVAL_MS = 60000  # Retry failed sensor init every 60s

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

    if errors:
        raise ValueError(
            "Config validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return True
