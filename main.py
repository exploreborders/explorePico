"""
Raspberry Pi Pico 2W - Home Assistant MQTT Integration
Clean, modular version with proper error handling
"""

import time
from umqtt.simple import MQTTClient
import machine
import ujson
import ubinascii
import micropython

from blink import blink_pattern, led
from wifi_utils import connect, is_connected
from updater_utils import log

from config import (
    WIFI_SSID,
    WIFI_PASSWORD,
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_USER,
    MQTT_PASSWORD,
    MQTT_SSL,
    DS18B20_PIN,
    ISNS20_CS_PIN,
    ISNS20_SPI_PORT,
    SENSOR_UPDATE_INTERVAL_MS,
    RECONNECT_DELAY_S,
    TEMP_CONVERSION_TIME_MS,
    SENSOR_RETRY_INTERVAL_MS,
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
    TOPIC_CURRENT_STATE,
    TOPIC_CURRENT_CONFIG,
    DEVICE_NAME,
    DEVICE_IDENTIFIER,
    INTERNAL_TEMP_ADC_PIN,
)

from sensors import DS18B20, DS18B20Manager, ISNS20, ISNS20Manager

micropython.alloc_emergency_exception_buf(200)

uid = ubinascii.hexlify(machine.unique_id()).decode()
MQTT_CLIENT_ID = f"pico_{uid}"

led.off()
temp_sensor = machine.ADC(INTERNAL_TEMP_ADC_PIN)

temp_sensors = DS18B20Manager(
    DS18B20(DS18B20_PIN), "DS18B20", SENSOR_RETRY_INTERVAL_MS
)
current_sensor = ISNS20Manager(
    ISNS20(ISNS20_CS_PIN, ISNS20_SPI_PORT), "ISNS20", SENSOR_RETRY_INTERVAL_MS
)

mqtt_client = None
led_state = False
last_sensor_publish = 0

# Track last published values for all MQTT topics
_last_mqtt_values = {}


def mqtt_publish(topic: str, value: str, retain: bool = True) -> bool:
    """Publish to MQTT only if value changed. Returns True if published."""
    global _last_mqtt_values

    key = (topic, retain)
    if _last_mqtt_values.get(key) != value:
        mqtt_client.publish(topic, value, retain=retain)
        _last_mqtt_values[key] = value
        return True
    return False


temp_sensors.set_logger(log)
current_sensor.set_logger(log)


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
        "device": get_device_info(),
    }


def get_temp_config() -> dict:
    """Return temperature sensor config for Home Assistant discovery."""
    return {
        "name": "Pico Temperature",
        "unique_id": "pico_temp",
        "state_topic": TOPIC_TEMP_STATE,
        "unit_of_measurement": "C",
        "device": get_device_info(),
    }


def get_room_temp_config() -> dict:
    """Return room temperature sensor config for Home Assistant discovery."""
    return {
        "name": "Pico Room Temperature",
        "unique_id": "pico_room_temp",
        "state_topic": TOPIC_ROOM_TEMP_STATE,
        "unit_of_measurement": "C",
        "device": get_device_info(),
    }


def get_water_temp_config() -> dict:
    """Return water temperature sensor config for Home Assistant discovery."""
    return {
        "name": "Pico Water Temperature",
        "unique_id": "pico_water_temp",
        "state_topic": TOPIC_WATER_TEMP_STATE,
        "unit_of_measurement": "C",
        "device": get_device_info(),
    }


def get_current_config() -> dict:
    """Return current sensor config for Home Assistant discovery."""
    return {
        "name": "Pico Current",
        "unique_id": "pico_current",
        "state_topic": TOPIC_CURRENT_STATE,
        "unit_of_measurement": "A",
        "device_class": "current",
        "device": get_device_info(),
    }


def publish_discovery() -> None:
    """Publish Home Assistant MQTT discovery configs."""
    led_config = ujson.dumps(get_led_config())
    temp_config = ujson.dumps(get_temp_config())
    room_temp_config = ujson.dumps(get_room_temp_config())
    water_temp_config = ujson.dumps(get_water_temp_config())
    current_config = ujson.dumps(get_current_config())

    log("MQTT", f"LED config: {len(led_config)} bytes")
    log("MQTT", f"Temp config: {len(temp_config)} bytes")
    log("MQTT", f"Room temp config: {len(room_temp_config)} bytes")
    log("MQTT", f"Water temp config: {len(water_temp_config)} bytes")
    log("MQTT", f"Current config: {len(current_config)} bytes")

    mqtt_client.publish(TOPIC_LED_CONFIG, led_config, retain=True)
    time.sleep(0.2)
    mqtt_client.publish(TOPIC_TEMP_CONFIG, temp_config, retain=True)
    time.sleep(0.2)
    mqtt_client.publish(TOPIC_ROOM_TEMP_CONFIG, room_temp_config, retain=True)
    time.sleep(0.2)
    mqtt_client.publish(TOPIC_WATER_TEMP_CONFIG, water_temp_config, retain=True)
    time.sleep(0.2)
    mqtt_client.publish(TOPIC_CURRENT_CONFIG, current_config, retain=True)
    time.sleep(0.2)


def publish_led_state() -> None:
    """Publish current LED state."""
    state = "ON" if led_state else "OFF"
    mqtt_publish(TOPIC_LED_STATE, state)


def publish_temperature() -> None:
    """Read and publish temperature."""
    temp = read_temperature()
    mqtt_publish(TOPIC_TEMP_STATE, str(temp))


def publish_room_temperature() -> None:
    """Read and publish room temperature from DS18B20 (first sensor)."""
    temps = temp_sensors.read(TEMP_CONVERSION_TIME_MS)
    if temps is not None and len(temps) > 0:
        temp = temps[0]
        if temp is not None:
            mqtt_publish(TOPIC_ROOM_TEMP_STATE, str(temp))
        elif temp_sensors.ever_connected:
            mqtt_publish(TOPIC_ROOM_TEMP_STATE, "unavailable")
    elif temp_sensors.ever_connected:
        mqtt_publish(TOPIC_ROOM_TEMP_STATE, "unavailable")


def publish_water_temperature() -> None:
    """Read and publish water temperature from DS18B20 (second sensor)."""
    temps = temp_sensors.read(TEMP_CONVERSION_TIME_MS)
    if temps is not None and len(temps) > 1:
        temp = temps[1]
        if temp is not None:
            mqtt_publish(TOPIC_WATER_TEMP_STATE, str(temp))
        elif temp_sensors.ever_connected:
            mqtt_publish(TOPIC_WATER_TEMP_STATE, "unavailable")
    elif temp_sensors.ever_connected:
        mqtt_publish(TOPIC_WATER_TEMP_STATE, "unavailable")


def publish_current() -> None:
    """Read and publish current from ISNS20 sensor."""
    current = current_sensor.read()
    if current is not None:
        mqtt_publish(TOPIC_CURRENT_STATE, str(current))
    elif current_sensor.ever_connected:
        mqtt_publish(TOPIC_CURRENT_STATE, "unavailable")


def on_message(topic: bytes, msg: bytes) -> None:
    """Handle incoming MQTT messages."""
    global led_state

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

    except Exception as e:
        log("ERROR", f"Message handling failed: {e}")


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

    client.set_callback(on_message)

    return client


def connect_mqtt() -> bool:
    """Connect to MQTT broker and set up subscriptions."""
    global mqtt_client

    log("MQTT", "Connecting...")
    blink_pattern("01")

    try:
        mqtt_client = create_mqtt_client()
        mqtt_client.connect()
        log("MQTT", "Connected!")

        time.sleep(1)
        mqtt_client.subscribe(TOPIC_LED_COMMAND)
        log("MQTT", "Subscribed!")

        time.sleep(1)
        publish_discovery()
        log("MQTT", "Discovery published!")

        time.sleep(0.5)
        publish_led_state()
        time.sleep(0.2)
        publish_temperature()

        log("MQTT", "Ready!")
        blink_pattern("11111")
        return True

    except Exception as e:
        log("ERROR", f"MQTT connection failed: {e}")
        blink_pattern("10000")
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


def handle_mqtt_message() -> None:
    """Check for and handle incoming MQTT messages."""
    mqtt_client.check_msg()


def handle_sensor_publish() -> None:
    """Publish temperature and current if interval has elapsed."""
    global last_sensor_publish

    now = time.ticks_ms()
    if time.ticks_diff(now, last_sensor_publish) >= SENSOR_UPDATE_INTERVAL_MS:
        publish_temperature()
        publish_room_temperature()
        publish_water_temperature()
        publish_current()
        last_sensor_publish = now


def run_main_loop() -> None:
    """Run the main MQTT loop."""
    global mqtt_client

    try:
        handle_mqtt_message()
        handle_sensor_publish()
        time.sleep(0.1)

    except OSError as e:
        log("WARN", f"Connection lost: {e}")
        blink_pattern("100")
        disconnect_mqtt()
        time.sleep(2)

    except Exception as e:
        err_str = str(e)
        if "closed" in err_str.lower() or "ECONNRESET" in err_str:
            log("WARN", "Connection closed by broker")
            blink_pattern("100")
            disconnect_mqtt()
            time.sleep(2)
        else:
            log("ERROR", f"Unexpected error: {e}")
            blink_pattern("1000")
            time.sleep(1)


def main() -> None:
    """Main entry point."""
    global last_sensor_publish, mqtt_client

    validate_config()

    log("BOOT", f"Starting Pico 2W MQTT Client - {uid}")

    blink_pattern("111111")

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
