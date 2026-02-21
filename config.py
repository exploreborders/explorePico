"""
Configuration for Pico 2W MQTT Client
"""

# MQTT Configuration
MQTT_SSL = True  # Enable SSL/TLS

# DS18B20 Configuration
DS18B20_PIN = 22  # GPIO pin for DS18B20 temperature sensor

# Timing
TEMP_UPDATE_INTERVAL_MS = 1000
RECONNECT_DELAY_S = 5
TEMP_CONVERSION_TIME_MS = 750  # DS18B20 conversion time

# Watchdog
WATCHDOG_TIMEOUT_MS = 8000  # 8 seconds - max on Pico is ~8388ms

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
