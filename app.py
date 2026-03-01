"""
Raspberry Pi Pico 2W - Home Assistant MQTT Integration

This is the main application that connects a Raspberry Pi Pico 2W to Home Assistant
via MQTT. It reads temperature and current sensors and publishes the data to MQTT
topics that Home Assistant automatically discovers.

Features:
    - MQTT integration with Home Assistant auto-discovery
    - DS18B20 temperature sensor support (multiple sensors on single GPIO)
    - ACS37030 current sensor support (5 sensors via ADS1115 I2C)
    - Internal RP2350 temperature sensor
    - OTA firmware updates via GitHub releases or SD card
    - LED control via MQTT
    - Device availability tracking (online/offline)
    - Automatic reconnection on network failure

Hardware:
    - Raspberry Pi Pico 2W (RP2350)
    - DS18B20 temperature sensors on GPIO22 (configurable)
    - ACS37030LLZATR-020B3 current sensors (5x) via ADS1115 I2C + Pico ADC

Usage:
    Upload all .py files to Pico and reset.
    The device will:
    1. Connect to WiFi
    2. Check for firmware updates (GitHub or SD card)
    3. Connect to MQTT broker
    4. Publish auto-discovery configs to Home Assistant
    5. Start publishing sensor data

    Sensors will automatically appear in Home Assistant.

Environment:
    MicroPython for Raspberry Pi Pico 2W
    Requires: umqtt.simple, onewire, ds18x20, sdcard
"""

# -----------------------------------------------------------------------------
# IMPORTS
# -----------------------------------------------------------------------------
import time
from umqtt.simple import MQTTClient
import machine
import ujson
import ubinascii
import micropython

from blink import blink_pattern, led
from wifi_utils import connect, is_connected
from updater_utils import log
from github_updater import check_and_update
from sensors import DS18B20, DS18B20Manager, ACS37030, ACS37030Manager
from sensors.ads1115 import ADS1115

from config import (
    WIFI_SSID,
    WIFI_PASSWORD,
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_USER,
    MQTT_PASSWORD,
    MQTT_SSL,
    DS18B20_PIN,
    ENABLE_ACS37030,
    ENABLE_ACS37030_PICO_ADC,
    ACS37030_I2C_ADDRESS,
    ACS37030_I2C_SCL_PIN,
    ACS37030_I2C_SDA_PIN,
    ACS37030_SENSITIVITY,
    ACS37030_ZERO_POINT,
    ACS37030_NUM_SENSORS,
    ACS37030_PICO_ADC_PIN,
    ACS37030_BUFFER_SIZE,
    GITHUB_OWNER,
    GITHUB_REPO,
    SENSOR_UPDATE_INTERVAL_MS,
    RECONNECT_DELAY_S,
    TEMP_CONVERSION_TIME_MS,
    SENSOR_RETRY_INTERVAL_MS,
    MQTT_DELAY_DISCOVERY,
    MQTT_DELAY_CONNECT,
    MQTT_DELAY_SUBSCRIBE,
    MQTT_DELAY_INITIAL_STATE,
    MQTT_LOOP_DELAY,
    ERROR_DELAY_SHORT,
    ERROR_DELAY_LONG,
    validate_config,
    TOPIC_LED_COMMAND,
    TOPIC_LED_STATE,
    TOPIC_LED_CONFIG,
    TOPIC_TEMP_STATE,
    TOPIC_TEMP_CONFIG,
    TOPIC_ROOM_TEMP_STATE,
    TOPIC_ROOM_TEMP_CONFIG,
    TOPIC_WATER_TEMP_STATE,
    TOPIC_WATER_TEMP_CONFIG,
    TOPIC_CURRENT_1_STATE,
    TOPIC_CURRENT_1_CONFIG,
    TOPIC_CURRENT_2_STATE,
    TOPIC_CURRENT_2_CONFIG,
    TOPIC_CURRENT_3_STATE,
    TOPIC_CURRENT_3_CONFIG,
    TOPIC_CURRENT_4_STATE,
    TOPIC_CURRENT_4_CONFIG,
    TOPIC_CURRENT_5_STATE,
    TOPIC_CURRENT_5_CONFIG,
    TOPIC_UPDATE_COMMAND,
    TOPIC_UPDATE_STATE,
    TOPIC_UPDATE_CONFIG,
    TOPIC_AVAILABILITY,
    DEVICE_NAME,
    DEVICE_IDENTIFIER,
    INTERNAL_TEMP_ADC_PIN,
)

# -----------------------------------------------------------------------------
# CONSTANTS & GLOBAL STATE
# -----------------------------------------------------------------------------
micropython.alloc_emergency_exception_buf(200)

uid = ubinascii.hexlify(machine.unique_id()).decode()
MQTT_CLIENT_ID = f"pico_{uid}"

# Sensor objects
temp_sensor = machine.ADC(INTERNAL_TEMP_ADC_PIN)
temp_sensors = DS18B20Manager(DS18B20(DS18B20_PIN), "DS18B20", SENSOR_RETRY_INTERVAL_MS)
temp_sensors.set_logger(log)

# ACS37030 current sensors (via ADS1115 I2C or Pico ADC)
ads1115 = None
current_sensors = []

if ENABLE_ACS37030:
    try:
        ads1115 = ADS1115(
            address=ACS37030_I2C_ADDRESS,
            scl_pin=ACS37030_I2C_SCL_PIN,
            sda_pin=ACS37030_I2C_SDA_PIN,
        )
        ads1115.set_logger(log)
        if ads1115.init():
            log("ADS1115 initialized successfully")
            # Create sensors for ADS1115 channels 0-3 (first 4 sensors)
            for i in range(min(ACS37030_NUM_SENSORS, 4)):
                sensor = ACS37030(
                    ads1115,
                    channel=i,
                    sensitivity=ACS37030_SENSITIVITY,
                    zero_point=ACS37030_ZERO_POINT,
                    is_pico_adc=False,
                )
                manager = ACS37030Manager(
                    sensor,
                    f"ACS37030_{i + 1}",
                    SENSOR_RETRY_INTERVAL_MS,
                    ACS37030_BUFFER_SIZE,
                )
                manager.set_logger(log)
                current_sensors.append(manager)
        else:
            log("ADS1115 init returned False, skipping sensors 1-4")
            ads1115 = None
    except Exception as e:
        log(f"ADS1115 not available: {e}")
        ads1115 = None

    # Create 5th sensor using Pico's built-in ADC (only if enabled)
    if ACS37030_NUM_SENSORS >= 5 and ENABLE_ACS37030_PICO_ADC:
        pico_adc = machine.ADC(ACS37030_PICO_ADC_PIN)
        sensor = ACS37030(
            pico_adc,
            channel=0,
            sensitivity=ACS37030_SENSITIVITY,
            zero_point=ACS37030_ZERO_POINT,
            is_pico_adc=True,
        )
        manager = ACS37030Manager(
            sensor, "ACS37030_5", SENSOR_RETRY_INTERVAL_MS, ACS37030_BUFFER_SIZE
        )
        manager.set_logger(log)
        current_sensors.append(manager)
    elif ACS37030_NUM_SENSORS >= 5 and not ENABLE_ACS37030_PICO_ADC:
        log("Sensor 5 disabled in config (ENABLE_ACS37030_PICO_ADC = False)")

led.off()

# MQTT state
mqtt_client = None
led_state = False
update_state = "idle"  # idle, checking, available, up_to_date, failed
last_sensor_publish = 0
_last_mqtt_values = {}


# -----------------------------------------------------------------------------
# MQTT HELPERS
# -----------------------------------------------------------------------------
def mqtt_publish(topic: str, value: str, retain: bool = True) -> bool:
    """Publish to MQTT only if value changed. Returns True if published."""
    global _last_mqtt_values

    key = (topic, retain)
    if _last_mqtt_values.get(key) != value:
        mqtt_client.publish(topic, value, retain=retain)
        _last_mqtt_values[key] = value
        return True
    return False


def _publish_sensor_value(
    read_func,
    state_topic: str,
    sensor_manager=None,
    sensor_index: int | None = None,
    needs_unavailable: bool = False,
) -> None:
    """Generic sensor publish with unavailable handling."""
    value = read_func()

    if sensor_index is not None and value is not None:
        if isinstance(value, list) and len(value) > sensor_index:
            value = value[sensor_index]
        else:
            value = None

    if value is not None:
        mqtt_publish(state_topic, str(value))
    elif needs_unavailable and sensor_manager and sensor_manager.ever_connected:
        mqtt_publish(state_topic, "unavailable")


# -----------------------------------------------------------------------------
# SENSOR FUNCTIONS
# -----------------------------------------------------------------------------
def read_temperature() -> float:
    """Read internal temperature sensor (RP2350).

    Uses RP2350 band-gap temperature sensor calibration:
    - 27°C baseline at 0V output
    - 0.706V reference voltage at 27°C
    - 0.001721 V/°C temperature coefficient
    """
    reading = temp_sensor.read_u16()
    voltage = reading * 3.3 / 65535
    temp_c = 27 - (voltage - 0.706) / 0.001721
    return round(temp_c, 1)


def connect_wifi() -> bool:
    """Connect to WiFi network with retry logic."""
    return connect(WIFI_SSID, WIFI_PASSWORD, log_fn=log, blink_fn=blink_pattern)


def ensure_wifi() -> bool:
    """Ensure WiFi is connected, reconnect if needed."""
    if is_connected():
        return True
    return connect_wifi()


# -----------------------------------------------------------------------------
# MQTT CONFIG GETTERS
# -----------------------------------------------------------------------------
def get_device_info() -> dict:
    """Return device info for Home Assistant discovery."""
    return {
        "identifiers": [DEVICE_IDENTIFIER],
        "name": DEVICE_NAME,
    }


def get_led_config() -> dict:
    """Return LED switch config for Home Assistant discovery."""
    return {
        "name": "Pico LED",
        "unique_id": "pico_led",
        "command_topic": TOPIC_LED_COMMAND,
        "state_topic": TOPIC_LED_STATE,
        "payload_on": "ON",
        "payload_off": "OFF",
        "availability": {
            "topic": TOPIC_AVAILABILITY,
            "payload_available": "online",
            "payload_not_available": "offline",
        },
        "device": get_device_info(),
    }


def get_temp_config() -> dict:
    """Return temperature sensor config for Home Assistant discovery."""
    return {
        "name": "Pico Temperature",
        "unique_id": "pico_temp",
        "state_topic": TOPIC_TEMP_STATE,
        "unit_of_measurement": "C",
        "availability": {
            "topic": TOPIC_AVAILABILITY,
            "payload_available": "online",
            "payload_not_available": "offline",
        },
        "device": get_device_info(),
    }


def get_room_temp_config() -> dict:
    """Return room temperature sensor config for Home Assistant discovery."""
    return {
        "name": "Pico Room Temperature",
        "unique_id": "pico_room_temp",
        "state_topic": TOPIC_ROOM_TEMP_STATE,
        "unit_of_measurement": "C",
        "availability": {
            "topic": TOPIC_AVAILABILITY,
            "payload_available": "online",
            "payload_not_available": "offline",
        },
        "device": get_device_info(),
    }


def get_water_temp_config() -> dict:
    """Return water temperature sensor config for Home Assistant discovery."""
    return {
        "name": "Pico Water Temperature",
        "unique_id": "pico_water_temp",
        "state_topic": TOPIC_WATER_TEMP_STATE,
        "unit_of_measurement": "C",
        "availability": {
            "topic": TOPIC_AVAILABILITY,
            "payload_available": "online",
            "payload_not_available": "offline",
        },
        "device": get_device_info(),
    }


# ACS37030 current sensor configs (5 sensors)
CURRENT_TOPICS = [
    (TOPIC_CURRENT_1_STATE, TOPIC_CURRENT_1_CONFIG, "Pico Current 1", "pico_current_1"),
    (TOPIC_CURRENT_2_STATE, TOPIC_CURRENT_2_CONFIG, "Pico Current 2", "pico_current_2"),
    (TOPIC_CURRENT_3_STATE, TOPIC_CURRENT_3_CONFIG, "Pico Current 3", "pico_current_3"),
    (TOPIC_CURRENT_4_STATE, TOPIC_CURRENT_4_CONFIG, "Pico Current 4", "pico_current_4"),
    (TOPIC_CURRENT_5_STATE, TOPIC_CURRENT_5_CONFIG, "Pico Current 5", "pico_current_5"),
]


def get_current_config(index: int) -> dict:
    """Return current sensor config for Home Assistant discovery."""
    state_topic, config_topic, name, unique_id = CURRENT_TOPICS[index]
    return {
        "name": name,
        "unique_id": unique_id,
        "state_topic": state_topic,
        "unit_of_measurement": "A",
        "device_class": "current",
        "availability": {
            "topic": TOPIC_AVAILABILITY,
            "payload_available": "online",
            "payload_not_available": "offline",
        },
        "device": get_device_info(),
    }


def get_update_config() -> dict:
    """Return update button config for Home Assistant discovery."""
    return {
        "name": "Pico Update",
        "unique_id": "pico_update",
        "command_topic": TOPIC_UPDATE_COMMAND,
        "state_topic": TOPIC_UPDATE_STATE,
        "availability": {
            "topic": TOPIC_AVAILABILITY,
            "payload_available": "online",
            "payload_not_available": "offline",
        },
        "device": get_device_info(),
    }


# -----------------------------------------------------------------------------
# REGISTRIES
# -----------------------------------------------------------------------------
SENSOR_REGISTRY = [
    {
        "name": "temperature",
        "read_func": read_temperature,
        "state_topic": TOPIC_TEMP_STATE,
        "needs_unavailable": False,
    },
    {
        "name": "room_temperature",
        "read_func": lambda: temp_sensors.read(TEMP_CONVERSION_TIME_MS),
        "state_topic": TOPIC_ROOM_TEMP_STATE,
        "sensor_index": 0,
        "sensor_manager": temp_sensors,
        "needs_unavailable": True,
    },
    {
        "name": "water_temperature",
        "read_func": lambda: temp_sensors.read(TEMP_CONVERSION_TIME_MS),
        "state_topic": TOPIC_WATER_TEMP_STATE,
        "sensor_index": 1,
        "sensor_manager": temp_sensors,
        "needs_unavailable": True,
    },
]

# Add ACS37030 current sensors
if ENABLE_ACS37030 and current_sensors:
    for i, sensor_manager in enumerate(current_sensors):
        state_topic, config_topic, _, _ = CURRENT_TOPICS[i]
        SENSOR_REGISTRY.append(
            {
                "name": f"current_{i + 1}",
                "read_func": sensor_manager.read,
                "state_topic": state_topic,
                "sensor_manager": sensor_manager,
                "needs_unavailable": True,
            }
        )

DISCOVERY_REGISTRY = [
    (TOPIC_LED_CONFIG, get_led_config),
    (TOPIC_TEMP_CONFIG, get_temp_config),
    (TOPIC_ROOM_TEMP_CONFIG, get_room_temp_config),
    (TOPIC_WATER_TEMP_CONFIG, get_water_temp_config),
    (TOPIC_UPDATE_CONFIG, get_update_config),
]

# Add ACS37030 current sensor discovery configs
if ENABLE_ACS37030:
    for i in range(len(current_sensors)):
        _, config_topic, _, _ = CURRENT_TOPICS[i]
        DISCOVERY_REGISTRY.append((config_topic, lambda idx=i: get_current_config(idx)))


# -----------------------------------------------------------------------------
# MQTT PUBLISH FUNCTIONS
# -----------------------------------------------------------------------------
def publish_all_sensors() -> None:
    """Publish all sensor values from registry."""
    for sensor in SENSOR_REGISTRY:
        _publish_sensor_value(
            read_func=sensor["read_func"],
            state_topic=sensor["state_topic"],
            sensor_manager=sensor.get("sensor_manager"),
            sensor_index=sensor.get("sensor_index"),
            needs_unavailable=sensor.get("needs_unavailable", False),
        )


def publish_discovery() -> None:
    """Publish Home Assistant MQTT discovery configs."""
    for topic, config_func in DISCOVERY_REGISTRY:
        payload = ujson.dumps(config_func())
        log("MQTT", f"{config_func.__name__}: {len(payload)} bytes")
        mqtt_client.publish(topic, payload, retain=True)
        time.sleep(MQTT_DELAY_DISCOVERY)


def publish_led_state() -> None:
    """Publish current LED state."""
    state = "ON" if led_state else "OFF"
    mqtt_publish(TOPIC_LED_STATE, state)


# -----------------------------------------------------------------------------
# MQTT CALLBACKS
# -----------------------------------------------------------------------------
def on_message(topic: bytes, msg: bytes) -> None:
    """Handle incoming MQTT messages."""
    global led_state, update_state

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
            publish_led_state()
            log("LED", msg_str)

        elif topic_str == TOPIC_UPDATE_COMMAND:
            # Accept PRESS (from HA button) or CHECK (manual)
            if msg_str in ("CHECK", "PRESS") and update_state == "idle":
                update_state = "checking"
                mqtt_publish(TOPIC_UPDATE_STATE, "checking")
                log("UPDATE", "Checking for updates...")
                success = check_and_update(GITHUB_OWNER, GITHUB_REPO)
                if success:
                    update_state = "available"
                    mqtt_publish(TOPIC_UPDATE_STATE, "available")
                else:
                    update_state = "up_to_date"
                    mqtt_publish(TOPIC_UPDATE_STATE, "up_to_date")

            # Accept UPDATE or PRESS when update is available
            elif msg_str in ("UPDATE", "PRESS") and update_state == "available":
                mqtt_publish(TOPIC_UPDATE_STATE, "rebooting")
                log("UPDATE", "Rebooting to apply update...")
                time.sleep(1)
                machine.reset()

    except Exception as e:
        log("ERROR", f"Message handling failed: {e}")


# -----------------------------------------------------------------------------
# MQTT CONNECTION
# -----------------------------------------------------------------------------
def create_mqtt_client() -> MQTTClient:
    """Create and configure MQTT client."""
    client = MQTTClient(
        client_id=MQTT_CLIENT_ID,
        server=MQTT_BROKER,
        port=MQTT_PORT,
        user=MQTT_USER,
        password=MQTT_PASSWORD,
        keepalive=30,
        ssl=MQTT_SSL,
    )

    client.set_last_will(TOPIC_AVAILABILITY, "offline", retain=True, qos=1)
    client.set_callback(on_message)

    return client


def connect_mqtt() -> bool:
    """Connect to MQTT broker and set up subscriptions."""
    global mqtt_client

    log("MQTT", "Connecting...")
    blink_pattern("10")

    try:
        mqtt_client = create_mqtt_client()
        mqtt_client.connect()
        mqtt_client.publish(TOPIC_AVAILABILITY, "online", retain=True)
        log("MQTT", "Connected!")

        time.sleep(MQTT_DELAY_CONNECT)
        mqtt_client.subscribe(TOPIC_LED_COMMAND)
        mqtt_client.subscribe(TOPIC_UPDATE_COMMAND)
        log("MQTT", "Subscribed!")

        time.sleep(MQTT_DELAY_SUBSCRIBE)
        publish_discovery()
        log("MQTT", "Discovery published!")

        time.sleep(MQTT_DELAY_INITIAL_STATE)
        publish_led_state()
        mqtt_publish(TOPIC_UPDATE_STATE, update_state)
        time.sleep(MQTT_DELAY_DISCOVERY)
        publish_all_sensors()

        log("MQTT", "Ready!")
        blink_pattern("1010")
        return True

    except Exception as e:
        log("ERROR", f"MQTT connection failed: {e}")
        blink_pattern("111")
        disconnect_mqtt()
        return False


def disconnect_mqtt() -> None:
    """Safely disconnect from MQTT broker."""
    global mqtt_client

    if mqtt_client is not None:
        try:
            mqtt_client.disconnect()
            log("MQTT", "Disconnected")
        except Exception as e:
            log("WARN", f"Disconnect error: {e}")
        finally:
            mqtt_client = None


# -----------------------------------------------------------------------------
# MAIN LOOP
# -----------------------------------------------------------------------------
def handle_mqtt_message() -> None:
    """Check for and handle incoming MQTT messages."""
    mqtt_client.check_msg()


def handle_sensor_publish() -> None:
    """Publish all sensor values if interval has elapsed."""
    global last_sensor_publish

    now = time.ticks_ms()
    if time.ticks_diff(now, last_sensor_publish) >= SENSOR_UPDATE_INTERVAL_MS:
        publish_all_sensors()
        last_sensor_publish = now


def run_main_loop() -> None:
    """Run the main MQTT loop."""
    global mqtt_client

    try:
        handle_mqtt_message()
        handle_sensor_publish()
        time.sleep(MQTT_LOOP_DELAY)

    except OSError as e:
        log("WARN", f"Connection lost: {e}")
        blink_pattern("111")
        disconnect_mqtt()
        time.sleep(ERROR_DELAY_LONG)

    except Exception as e:
        err_str = str(e)
        if "closed" in err_str.lower() or "ECONNRESET" in err_str:
            log("WARN", "Connection closed by broker")
            blink_pattern("111")
            disconnect_mqtt()
            time.sleep(ERROR_DELAY_LONG)
        else:
            log("ERROR", f"Unexpected error: {e}")
            blink_pattern("111")
            time.sleep(ERROR_DELAY_SHORT)


# -----------------------------------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------------------------------
def main() -> None:
    """Main entry point."""
    global last_sensor_publish, mqtt_client

    validate_config()

    log("BOOT", f"Starting Pico 2W MQTT Client - {uid}")

    blink_pattern("11011")

    disconnect_mqtt()

    reconnect_count = 0

    while True:
        if not ensure_wifi():
            time.sleep(RECONNECT_DELAY_S)
            continue

        if mqtt_client is None:
            if not connect_mqtt():
                reconnect_count += 1
                delay = min(RECONNECT_DELAY_S * reconnect_count, 30)
                log("MQTT", f"Reconnect in {delay}s (attempt {reconnect_count})")
                time.sleep(delay)
                if reconnect_count > 5:
                    reconnect_count = 0
                continue
            reconnect_count = 0

        run_main_loop()


if __name__ == "__main__":
    main()
