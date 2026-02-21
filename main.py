"""
Raspberry Pi Pico 2W - Home Assistant MQTT Integration
Clean, modular version with proper error handling
"""

import network
import time
from umqtt.simple import MQTTClient
import machine
import ujson
import ubinascii
import micropython

from config import (
    WIFI_SSID,
    WIFI_PASSWORD,
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_USER,
    MQTT_PASSWORD,
    MQTT_SSL,
    DS18B20_PIN,
    DS18B20_PIN_2,
    TEMP_UPDATE_INTERVAL_MS,
    RECONNECT_DELAY_S,
    TEMP_CONVERSION_TIME_MS,
    SENSOR_RETRY_INTERVAL_MS,
)

from sensors.ds18b20 import DS18B20

micropython.alloc_emergency_exception_buf(200)

uid = ubinascii.hexlify(machine.unique_id()).decode()
MQTT_CLIENT_ID = f"pico_{uid}"

TOPIC_LED_COMMAND = "pico/led/set"
TOPIC_LED_STATE = "pico/led/state"
TOPIC_LED_CONFIG = "homeassistant/switch/pico_led/config"

TOPIC_TEMP_STATE = "pico/temperature"
TOPIC_TEMP_CONFIG = "homeassistant/sensor/pico_temp/config"

TOPIC_ROOM_TEMP_STATE = "pico/room_temp"
TOPIC_ROOM_TEMP_CONFIG = "homeassistant/sensor/pico_room_temp/config"

TOPIC_WATER_TEMP_STATE = "pico/water_temp"
TOPIC_WATER_TEMP_CONFIG = "homeassistant/sensor/pico_water_temp/config"

led = machine.Pin("LED", machine.Pin.OUT)
led.off()
temp_sensor = machine.ADC(4)
wlan = network.WLAN(network.STA_IF)

ds18b20 = DS18B20(DS18B20_PIN)
ds18b20_2 = DS18B20(DS18B20_PIN_2)
ds18b20_initialized = False
ds18b20_2_initialized = False
ds18b20_ever_connected = False
ds18b20_2_ever_connected = False
ds18b20_conversion_start = 0
ds18b20_2_conversion_start = 0
ds18b20_last_retry = 0
ds18b20_2_last_retry = 0

mqtt_client = None
led_state = False
last_temp_publish = 0
wifi_connected = False
mqtt_connected = False


def blink(times: int, delay: float = 0.15, pause: float = 0.3) -> None:
    """Visual feedback via onboard LED."""
    for i in range(times):
        led.on()
        time.sleep(delay)
        led.off()
        if i < times - 1:
            time.sleep(pause)


def blink_pattern(pattern: str) -> None:
    """Blink LED according to pattern string (e.g., "1010" = on-off-on-off)."""
    for char in pattern:
        if char == "1":
            led.on()
        else:
            led.off()
        time.sleep(0.15)
    led.off()
    time.sleep(0.3)


def log(tag: str, message: str) -> None:
    """Simple logging with tag prefix."""
    print(f"[{tag}] {message}")


def read_temperature() -> float:
    """Read internal temperature sensor (RP2350)."""
    reading = temp_sensor.read_u16()
    voltage = reading * 3.3 / 65535
    temp_c = 27 - (voltage - 0.706) / 0.001721
    return round(temp_c, 1)


def read_room_temperature() -> float | None:
    """Read external DS18B20 temperature sensor using non-blocking reads with auto-retry."""
    global ds18b20_initialized, ds18b20_conversion_start, ds18b20_ever_connected
    global ds18b20_last_retry

    now = time.ticks_ms()

    if not ds18b20_initialized:
        should_retry = ds18b20_last_retry == 0
        if not should_retry:
            elapsed = time.ticks_diff(now, ds18b20_last_retry)
            should_retry = elapsed >= SENSOR_RETRY_INTERVAL_MS

        if should_retry:
            log("DS18B20", "Initializing...")
            ds18b20_initialized = ds18b20.init()
            if not ds18b20_initialized:
                ds18b20_last_retry = now
                log("DS18B20", "Init failed! Retrying in 60s...")
                return None
            ds18b20_ever_connected = True
            ds18b20_last_retry = now
            log("DS18B20", "Initialized successfully")
            time.sleep_ms(750)
            temp = ds18b20.read(start_conversion=False)
            if temp is not None:
                ds18b20.start_conversion()
                ds18b20_conversion_start = time.ticks_ms()
            return temp
        return None

    elapsed = time.ticks_diff(now, ds18b20_conversion_start)
    if elapsed >= TEMP_CONVERSION_TIME_MS:
        temp = ds18b20.read(start_conversion=False)
        if temp is not None:
            ds18b20.start_conversion()
            ds18b20_conversion_start = time.ticks_ms()
            return temp
        else:
            log("DS18B20", "Sensor disconnected")
            ds18b20_initialized = False
            ds18b20_last_retry = 0
            return None

    return ds18b20.get_last_value()


def read_water_temperature() -> float | None:
    """Read second DS18B20 temperature sensor (water temp) with auto-retry."""
    global ds18b20_2_initialized, ds18b20_2_conversion_start, ds18b20_2_ever_connected
    global ds18b20_2_last_retry

    now = time.ticks_ms()

    if not ds18b20_2_initialized:
        should_retry = ds18b20_2_last_retry == 0
        if not should_retry:
            elapsed = time.ticks_diff(now, ds18b20_2_last_retry)
            should_retry = elapsed >= SENSOR_RETRY_INTERVAL_MS

        if should_retry:
            log("DS18B20-2", "Initializing...")
            ds18b20_2_initialized = ds18b20_2.init()
            if not ds18b20_2_initialized:
                ds18b20_2_last_retry = now
                log("DS18B20-2", "Init failed! Retrying in 60s...")
                return None
            ds18b20_2_ever_connected = True
            ds18b20_2_last_retry = now
            log("DS18B20-2", "Initialized successfully")
            time.sleep_ms(750)
            temp = ds18b20_2.read(start_conversion=False)
            if temp is not None:
                ds18b20_2.start_conversion()
                ds18b20_2_conversion_start = time.ticks_ms()
            return temp
        return None

    elapsed = time.ticks_diff(now, ds18b20_2_conversion_start)
    if elapsed >= TEMP_CONVERSION_TIME_MS:
        temp = ds18b20_2.read(start_conversion=False)
        if temp is not None:
            ds18b20_2.start_conversion()
            ds18b20_2_conversion_start = time.ticks_ms()
            return temp
        else:
            log("DS18B20-2", "Sensor disconnected")
            ds18b20_2_initialized = False
            ds18b20_2_last_retry = 0
            return None

    return ds18b20_2.get_last_value()


def connect_wifi() -> bool:
    """Connect to WiFi network with retry logic."""
    global wifi_connected
    log("WiFi", "Connecting...")
    blink_pattern("10")
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    for attempt in range(30):
        if wlan.isconnected():
            wifi_connected = True
            log("WiFi", f"Connected! IP: {wlan.ifconfig()[0]}")
            blink_pattern("111")
            return True
        time.sleep(1)

    wifi_connected = False
    log("WiFi", "Failed to connect")
    blink_pattern("1000")
    return False


def ensure_wifi() -> bool:
    """Ensure WiFi is connected, reconnect if needed."""
    global wifi_connected
    if wlan.isconnected():
        wifi_connected = True
        return True
    wifi_connected = False
    return connect_wifi()


def get_device_info() -> dict:
    """Return device info for Home Assistant discovery."""
    return {
        "identifiers": ["pico2w"],
        "name": "Raspberry Pi Pico 2W",
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


def publish_discovery() -> None:
    """Publish Home Assistant MQTT discovery configs."""
    led_config = ujson.dumps(get_led_config())
    temp_config = ujson.dumps(get_temp_config())
    room_temp_config = ujson.dumps(get_room_temp_config())

    log("MQTT", f"LED config: {len(led_config)} bytes")
    log("MQTT", f"Temp config: {len(temp_config)} bytes")
    log("MQTT", f"Room temp config: {len(room_temp_config)} bytes")

    mqtt_client.publish(TOPIC_LED_CONFIG, led_config, retain=True)
    time.sleep(0.2)
    mqtt_client.publish(TOPIC_TEMP_CONFIG, temp_config, retain=True)
    time.sleep(0.2)
    mqtt_client.publish(TOPIC_ROOM_TEMP_CONFIG, room_temp_config, retain=True)
    time.sleep(0.2)

    water_temp_config = ujson.dumps(get_water_temp_config())
    log("MQTT", f"Water temp config: {len(water_temp_config)} bytes")
    mqtt_client.publish(TOPIC_WATER_TEMP_CONFIG, water_temp_config, retain=True)
    time.sleep(0.2)


def publish_led_state() -> None:
    """Publish current LED state."""
    state = "ON" if led_state else "OFF"
    mqtt_client.publish(TOPIC_LED_STATE, state, retain=True)


def publish_temperature() -> None:
    """Read and publish temperature."""
    temp = read_temperature()
    mqtt_client.publish(TOPIC_TEMP_STATE, str(temp), retain=True)


def publish_room_temperature() -> None:
    """Read and publish room temperature from DS18B20."""
    global ds18b20_ever_connected
    temp = read_room_temperature()
    if temp is not None:
        mqtt_client.publish(TOPIC_ROOM_TEMP_STATE, str(temp), retain=True)
    elif ds18b20_ever_connected:
        mqtt_client.publish(TOPIC_ROOM_TEMP_STATE, "unavailable", retain=True)


def publish_water_temperature() -> None:
    """Read and publish water temperature from second DS18B20."""
    global ds18b20_2_ever_connected
    temp = read_water_temperature()
    if temp is not None:
        mqtt_client.publish(TOPIC_WATER_TEMP_STATE, str(temp), retain=True)
    elif ds18b20_2_ever_connected:
        mqtt_client.publish(TOPIC_WATER_TEMP_STATE, "unavailable", retain=True)


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
    global mqtt_client, mqtt_connected

    log("MQTT", "Connecting...")
    blink_pattern("01")

    try:
        mqtt_client = create_mqtt_client()
        mqtt_client.connect()
        mqtt_connected = True
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
        mqtt_connected = False
        log("ERROR", f"MQTT connection failed: {e}")
        blink_pattern("10000")
        disconnect_mqtt()
        return False


def disconnect_mqtt() -> None:
    """Safely disconnect from MQTT broker."""
    global mqtt_client, mqtt_connected

    if mqtt_client is not None:
        try:
            mqtt_client.disconnect()
            log("MQTT", "Disconnected")
        except Exception as e:
            log("WARN", f"Disconnect error: {e}")
        finally:
            mqtt_client = None
            mqtt_connected = False


def handle_mqtt_message() -> None:
    """Check for and handle incoming MQTT messages."""
    mqtt_client.check_msg()


def handle_temperature_publish() -> None:
    """Publish temperature if interval has elapsed."""
    global last_temp_publish

    now = time.ticks_ms()
    if time.ticks_diff(now, last_temp_publish) >= TEMP_UPDATE_INTERVAL_MS:
        publish_temperature()
        publish_room_temperature()
        publish_water_temperature()
        last_temp_publish = now


def run_main_loop() -> None:
    """Run the main MQTT loop."""
    global mqtt_client, mqtt_connected

    try:
        handle_mqtt_message()
        handle_temperature_publish()
        time.sleep(0.1)

    except OSError as e:
        mqtt_connected = False
        log("WARN", f"Connection lost: {e}")
        blink_pattern("100")
        disconnect_mqtt()
        time.sleep(2)

    except Exception as e:
        err_str = str(e)
        mqtt_connected = False
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
    global last_temp_publish, mqtt_client

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
