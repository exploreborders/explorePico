"""
Configuration for Pico 2W MQTT Client
"""

# MQTT Configuration
MQTT_SSL = True  # Enable SSL/TLS

# DS18B20 Configuration
DS18B20_PIN = 22  # GPIO pin for DS18B20 temperature sensor
DS18B20_PIN_2 = 21  # GPIO pin for second DS18B20 (water temp)

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
