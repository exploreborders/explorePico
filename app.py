"""
Raspberry Pi Pico 2W - Home Assistant MQTT Integration

This is the main application that connects a Raspberry Pi Pico 2W to Home Assistant
via MQTT. It reads temperature, current, and GPS sensors and publishes the data
to MQTT topics. Sensor definitions are in the Home Assistant YAML package file.

Features:
    - MQTT integration with Home Assistant (sensors defined in YAML package)
    - DS18B20 temperature sensor support (multiple sensors on single GPIO)
    - ACS37030 current sensor support (5 sensors via ADS1115 I2C)
    - Internal RP2350 temperature sensor
    - SIM7600G-H LTE/GPS support (4G connection + GPS positioning)
    - OTA firmware updates via GitHub releases or SD card
    - LED control via MQTT
    - Device availability tracking (online/offline)
    - Automatic reconnection on network failure

Hardware:
    - Raspberry Pi Pico 2W (RP2350)
    - DS18B20 temperature sensors on GPIO22 (configurable)
    - ACS37030LLZATR-020B3 current sensors (5x) via ADS1115 I2C + Pico ADC
    - SIM7600G-H LTE module (UART GP0/GP1)

Usage:
    1. Copy homeassistant/pico2w_sensors.yaml to HA config/packages/
    2. Add to HA configuration.yaml:
       homeassistant:
         packages: !include_dir_named packages
    3. Upload all .py files to Pico and reset.
    4. Restart Home Assistant.

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
from wifi_utils import scan_and_connect, is_connected
from updater_utils import log, read_version
from github_updater import check_and_update
from relay_utils import RelayManager
from sensors import DS18B20, DS18B20Manager, ACS37030, ACS37030Manager
from sensors.ads1115 import ADS1115

try:
    from lte_utils import (
        is_lte_connected,
        get_gps_location,
        get_signal_info,
        get_network_info,
        init_gps,
        sync_time,
        get_lte_manager,
    )

    LTE_AVAILABLE = True
except ImportError:
    LTE_AVAILABLE = False
    sync_time = None
    get_lte_manager = None

# Import SIM7600MQTT for LTE connections
if LTE_AVAILABLE:
    try:
        from sim7600_mqtt import SIM7600MQTT

        log("LTE", "SIM7600MQTT imported successfully")
    except Exception as e:
        log("LTE", f"SIM7600MQTT import failed: {e}")
        SIM7600MQTT = None
else:
    SIM7600MQTT = None

from config import (
    WIFI_SSID,
    WIFI_PASSWORD,
    WIFI_SSID_2,
    WIFI_PASSWORD_2,
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
    ACS37030_I2C_ID,
    ACS37030_SENSITIVITY,
    ACS37030_ZERO_POINT,
    ACS37030_ZERO_OFFSET,
    ACS37030_NUM_SENSORS,
    ACS37030_PICO_ADC_PIN,
    ACS37030_BUFFER_SIZE,
    GITHUB_OWNER,
    GITHUB_REPO,
    SENSOR_UPDATE_INTERVAL_MS,
    RECONNECT_DELAY_S,
    TEMP_CONVERSION_TIME_MS,
    SENSOR_RETRY_INTERVAL_MS,
    MQTT_DELAY_CONNECT,
    MQTT_DELAY_INITIAL_STATE,
    MQTT_LOOP_DELAY,
    ERROR_DELAY_SHORT,
    ERROR_DELAY_LONG,
    validate_config,
    TOPIC_LED_COMMAND,
    TOPIC_LED_STATE,
    TOPIC_TEMP_STATE,
    TOPIC_ROOM_TEMP_STATE,
    TOPIC_WATER_TEMP_STATE,
    TOPIC_CURRENT_1_STATE,
    TOPIC_CURRENT_2_STATE,
    TOPIC_CURRENT_3_STATE,
    TOPIC_CURRENT_4_STATE,
    TOPIC_CURRENT_5_STATE,
    TOPIC_UPDATE_CMD,
    TOPIC_UPDATE_STATE,
    TOPIC_UPDATE_LATEST,
    TOPIC_AVAILABILITY,
    INTERNAL_TEMP_ADC_PIN,
    ENABLE_GPS,
    GPS_UPDATE_INTERVAL_MS,
    SIGNAL_UPDATE_INTERVAL_MS,
    NETWORK_INFO_UPDATE_INTERVAL_MS,
    TOPIC_CONNECTION_TYPE,
    TOPIC_SIGNAL_RSSI,
    TOPIC_SIGNAL_QUALITY,
    TOPIC_NETWORK_OPERATOR,
    TOPIC_NETWORK_TYPE,
    TOPIC_DEVICE_TRACKER,
    LTE_UART_ID,
    LTE_TX_PIN,
    LTE_RX_PIN,
    LTE_RTS_PIN,
    LTE_CTS_PIN,
    LTE_BAUD,
    RELAY_1_PIN,
    RELAY_2_PIN,
    RELAY_3_PIN,
    RELAY_4_PIN,
    TOPIC_RELAY_1_COMMAND,
    TOPIC_RELAY_1_STATE,
    TOPIC_RELAY_2_COMMAND,
    TOPIC_RELAY_2_STATE,
    TOPIC_RELAY_3_COMMAND,
    TOPIC_RELAY_3_STATE,
    TOPIC_RELAY_4_COMMAND,
    TOPIC_RELAY_4_STATE,
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
            i2c_id=ACS37030_I2C_ID,
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
                    zero_point_offset=ACS37030_ZERO_OFFSET,
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

relay_manager = RelayManager([RELAY_1_PIN, RELAY_2_PIN, RELAY_3_PIN, RELAY_4_PIN])
relay_manager.set_logger(log)

RELAY_COMMAND_TOPICS = [
    TOPIC_RELAY_1_COMMAND,
    TOPIC_RELAY_2_COMMAND,
    TOPIC_RELAY_3_COMMAND,
    TOPIC_RELAY_4_COMMAND,
]

RELAY_STATE_TOPICS = [
    TOPIC_RELAY_1_STATE,
    TOPIC_RELAY_2_STATE,
    TOPIC_RELAY_3_STATE,
    TOPIC_RELAY_4_STATE,
]

# MQTT state
mqtt_client = None
led_state = False
update_state = "Update Pico"
latest_version_received = None
last_sensor_publish = 0
_last_mqtt_values = {}
reconnect_count = 0

# LTE/GPS state
last_gps_publish = 0
_last_gps_fix: dict | None = None
last_signal_publish = 0
last_network_publish = 0
last_connection_type_publish = 0
connection_type = "offline"
_gps_available = False

# Time sync state
time_synced = False


# -----------------------------------------------------------------------------
# MQTT HELPERS
# -----------------------------------------------------------------------------
def mqtt_publish(topic: str, value: str, retain: bool = True) -> bool:
    """Publish to MQTT only if value changed. Returns True if published."""
    global _last_mqtt_values

    key = (topic, retain)
    if _last_mqtt_values.get(key) != value:
        try:
            mqtt_client.publish(topic, value, retain=retain)
        except (OSError, AttributeError):
            return False
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
        # Round current sensors to reduce publishes
        if "current_" in state_topic:
            value = round(float(value), 1)  # 1 decimal place
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
    """Connect to WiFi network with retry logic. Tries multiple networks."""
    networks = [(WIFI_SSID, WIFI_PASSWORD)]
    if WIFI_SSID_2 and WIFI_PASSWORD_2:
        networks.append((WIFI_SSID_2, WIFI_PASSWORD_2))
    return scan_and_connect(networks, log_fn=log, blink_fn=blink_pattern)


def ensure_wifi() -> bool:
    """Ensure WiFi is connected, reconnect if needed."""
    if is_connected():
        return True
    return connect_wifi()


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
CURRENT_STATE_TOPICS = [
    TOPIC_CURRENT_1_STATE,
    TOPIC_CURRENT_2_STATE,
    TOPIC_CURRENT_3_STATE,
    TOPIC_CURRENT_4_STATE,
    TOPIC_CURRENT_5_STATE,
]


if ENABLE_ACS37030 and current_sensors:
    for i, sensor_manager in enumerate(current_sensors):
        SENSOR_REGISTRY.append(
            {
                "name": f"current_{i + 1}",
                "read_func": lambda idx=i: _read_current_with_offset(idx),
                "state_topic": CURRENT_STATE_TOPICS[i],
                "sensor_manager": sensor_manager,
                "needs_unavailable": True,
            }
        )


# -----------------------------------------------------------------------------
# MQTT PUBLISH FUNCTIONS
# -----------------------------------------------------------------------------
def _read_current_with_offset(index: int) -> float | None:
    """Read current sensor value.

    Note: Offset is now handled in Home Assistant via template sensors.

    Args:
        index: Sensor index (0-4)

    Returns:
        Current value in Amps, or None if not available
    """
    if index < len(current_sensors):
        raw = current_sensors[index].read()
        if raw is not None:
            return round(raw, 2)
    return None


def publish_all_sensors() -> None:
    """Publish all sensor values from registry.

    Reads all sensors first, then publishes all values.
    Checks for incoming messages once after the batch.
    """
    for sensor in SENSOR_REGISTRY:
        _publish_sensor_value(
            read_func=sensor["read_func"],
            state_topic=sensor["state_topic"],
            sensor_manager=sensor.get("sensor_manager"),
            sensor_index=sensor.get("sensor_index"),
            needs_unavailable=sensor.get("needs_unavailable", False),
        )
    # Single message check after the entire batch (reduces UART overhead)
    if mqtt_client:
        mqtt_client.check_msg()


def publish_led_state() -> None:
    """Publish current LED state."""
    state = "ON" if led_state else "OFF"
    mqtt_publish(TOPIC_LED_STATE, state)


def publish_version(
    installed_version: str,
    latest_version: str = None,
    in_progress: bool = False,
    percentage: int = None,
) -> None:
    """Publish version info to HA update entity.

    Args:
        installed_version: Current installed firmware version
        latest_version: Latest available version (from GitHub webhook)
        in_progress: True if update is currently running
        percentage: Update progress 0-100 (optional)
    """
    global latest_version_received

    if latest_version:
        latest_version_received = latest_version

    state = {
        "installed_version": installed_version,
        "latest_version": latest_version_received
        if latest_version_received
        else installed_version,
        "in_progress": in_progress,
    }

    if percentage is not None:
        state["update_percentage"] = percentage

    if mqtt_client is None:
        return
    try:
        mqtt_client.publish(TOPIC_UPDATE_STATE, ujson.dumps(state), retain=True)
    except OSError:
        pass


def update_version_received(latest: str) -> None:
    """Handle new version received from GitHub webhook."""
    global latest_version_received
    latest_version_received = latest
    log("UPDATE", f"Latest version received: {latest}")
    # Publish updated version info
    current = read_version() or "0.0"
    publish_version(current, latest, False)


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

        elif topic_str in RELAY_COMMAND_TOPICS:
            relay_index = RELAY_COMMAND_TOPICS.index(topic_str)
            if msg_str == "ON":
                relay_manager.set_relay(relay_index, True)
            elif msg_str == "OFF":
                relay_manager.set_relay(relay_index, False)
            state = "ON" if relay_manager.get_relay(relay_index) else "OFF"
            mqtt_publish(RELAY_STATE_TOPICS[relay_index], state)
            log("RELAY", f"Relay {relay_index + 1}: {state}")

        elif topic_str == TOPIC_UPDATE_CMD:
            # User clicked "Update installieren" in HA
            if msg_str in ("PRESS", "INSTALL") and update_state == "Update Pico":
                log("UPDATE", "Starting update from HA...")

                # If on LTE, temporarily connect WiFi for urequests
                was_on_lte = LTE_AVAILABLE and is_lte_connected()
                if was_on_lte:
                    log("UPDATE", "On LTE, connecting WiFi for update...")
                    if not ensure_wifi():
                        log("UPDATE", "WiFi connection failed, cannot update")
                        update_state = "Update Pico"
                        return

                # Progress callback for update process
                def progress_callback(percent: int, status: str) -> None:
                    global update_state
                    update_state = status
                    current = read_version() or "0.0"
                    latest = latest_version_received or current
                    in_progress = status not in ("up_to_date", "error")
                    publish_version(
                        current, latest, in_progress, percent if in_progress else None
                    )

                # Start update process
                try:
                    success = check_and_update(
                        GITHUB_OWNER, GITHUB_REPO, progress_callback
                    )
                except Exception as e:
                    log("UPDATE", f"Update error: {e}")
                    success = False
                    update_state = "Update Pico"
                finally:
                    # Drop WiFi if we were on LTE — main loop will restore LTE
                    if was_on_lte:
                        log("UPDATE", "Dropping WiFi, returning to LTE...")
                        try:
                            import network

                            network.WLAN(network.STA_IF).disconnect()
                        except OSError:
                            pass

                # This only runs if update failed (no reboot)
                if not success:
                    current = read_version() or "0.0"
                    latest = latest_version_received or current
                    if update_state == "up_to_date":
                        publish_version(current, latest, False, 100)
                        time.sleep(5)
                        publish_version(current, latest, False)
                    else:
                        publish_version(current, latest, False, 0)
                        time.sleep(5)
                        publish_version(current, latest, False)
                    update_state = "Update Pico"

        elif topic_str == TOPIC_UPDATE_LATEST:
            # GitHub webhook sent new latest version
            try:
                latest = msg.decode().strip().lstrip("v")
                if latest:
                    log("UPDATE", f"New version available: {latest}")
                    update_version_received(latest)
            except Exception as e:
                log("ERROR", f"Failed to parse latest version: {e}")

    except Exception as e:
        log("ERROR", f"Message handling failed: {e}")


# -----------------------------------------------------------------------------
# MQTT CONNECTION
# -----------------------------------------------------------------------------
def create_mqtt_client():
    """Create and configure MQTT client.

    Uses SIM7600MQTT for LTE connections, umqtt.simple for WiFi.
    """
    global connection_type

    # Check actual connection state (don't rely on connection_type variable)
    is_lte = LTE_AVAILABLE and is_lte_connected()
    is_wifi = is_connected()

    log("MQTT", f"Connection state: LTE={is_lte}, WiFi={is_wifi}")
    log("MQTT", f"SIM7600MQTT available: {SIM7600MQTT is not None}")

    # Use SIM7600's built-in MQTT for LTE connections
    if is_lte and SIM7600MQTT and get_lte_manager:
        lte_mgr = get_lte_manager()
        log("MQTT", f"LTE manager: {lte_mgr is not None}")
        if lte_mgr:
            sim = lte_mgr.sim
            log("MQTT", "Using SIM7600 MQTT client (non-SSL for LTE)")
            connection_type = "LTE"
            # Use plain MQTT port 1883 for LTE (no SSL support)
            client = SIM7600MQTT(
                sim=sim,
                client_id=MQTT_CLIENT_ID,
                server=MQTT_BROKER,
                port=1883,  # Plain MQTT port
                user=MQTT_USER,
                password=MQTT_PASSWORD,
                keepalive=60,
                ssl=False,
            )
            client.set_callback(on_message)
            return client

    # Use umqtt.simple for WiFi connections (supports SSL)
    log("MQTT", "Using umqtt.simple client")
    connection_type = "WiFi" if is_wifi else "offline"
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

        # Check if connect() succeeds
        # umqtt.simple returns 0 (CONNACK code) on success; SIM7600MQTT returns True.
        # Both raise exceptions on failure — caught below.
        try:
            log("MQTT", f"Attempting connection to {MQTT_BROKER}:{MQTT_PORT}...")
            result = mqtt_client.connect()
            # 0 = success (CONNACK return code), True = success (SIM7600MQTT)
            if result != 0 and result is not True:
                log("MQTT", f"Connection failed! Result: {result}")
                mqtt_client = None
                return False
        except Exception as e:
            log("MQTT", f"Connection error: {e}")
            mqtt_client = None
            return False

        # Only wait for SSL handshake if using SSL (WiFi). LTE uses plain MQTT.
        if MQTT_SSL:
            time.sleep(1)
        mqtt_client.publish(TOPIC_AVAILABILITY, "online", retain=True)
        log("MQTT", "Connected!")

        time.sleep(MQTT_DELAY_CONNECT)
        mqtt_client.subscribe(TOPIC_LED_COMMAND)
        mqtt_client.subscribe(TOPIC_UPDATE_CMD)
        mqtt_client.subscribe(TOPIC_UPDATE_LATEST)
        for topic in RELAY_COMMAND_TOPICS:
            mqtt_client.subscribe(topic)
        log("MQTT", "Subscribed!")

        time.sleep(MQTT_DELAY_INITIAL_STATE)
        publish_led_state()
        for i, topic in enumerate(RELAY_STATE_TOPICS):
            state = "ON" if relay_manager.get_relay(i) else "OFF"
            mqtt_publish(topic, state)
        # Initial version publish: read from flash and send to HA
        current_version = read_version() or "0.0"
        publish_version(current_version, current_version, False)
        publish_all_sensors()

        # Small delay to ensure all initial states are sent before main loop
        time.sleep(0.2)

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
    global mqtt_client, _last_mqtt_values

    if mqtt_client is not None:
        try:
            mqtt_client.disconnect()
            log("MQTT", "Disconnected")
        except Exception as e:
            log("WARN", f"Disconnect error: {e}")
        finally:
            mqtt_client = None
            # Clear cached values so all sensors are republished after reconnect
            _last_mqtt_values.clear()


# -----------------------------------------------------------------------------
# MAIN LOOP
# -----------------------------------------------------------------------------
def handle_mqtt_message() -> None:
    """Check for and handle incoming MQTT messages."""
    if mqtt_client is None:
        return
    mqtt_client.check_msg()


def handle_sensor_publish() -> None:
    """Publish all sensor values if interval has elapsed."""
    global last_sensor_publish

    now = time.ticks_ms()
    interval = SENSOR_UPDATE_INTERVAL_MS

    if time.ticks_diff(now, last_sensor_publish) >= interval:
        publish_all_sensors()
        last_sensor_publish = now


def handle_connection_type_publish() -> None:
    """Publish connection type (LTE/WiFi/offline)."""
    global connection_type, last_connection_type_publish

    now = time.ticks_ms()
    if time.ticks_diff(now, last_connection_type_publish) < SIGNAL_UPDATE_INTERVAL_MS:
        return

    if LTE_AVAILABLE and is_lte_connected():
        connection_type = "LTE"
    elif is_connected():
        connection_type = "WiFi"
    else:
        connection_type = "offline"

    mqtt_publish(TOPIC_CONNECTION_TYPE, connection_type)
    last_connection_type_publish = now


def handle_lte_signal_publish() -> None:
    """Publish LTE signal quality if LTE is connected."""
    global last_signal_publish

    now = time.ticks_ms()
    if time.ticks_diff(now, last_signal_publish) < SIGNAL_UPDATE_INTERVAL_MS:
        return

    if not LTE_AVAILABLE or not is_lte_connected():
        return

    signal = get_signal_info()
    rssi = signal.get("rssi", 0)
    if rssi == -999:
        mqtt_publish(TOPIC_SIGNAL_RSSI, "unavailable")
    else:
        mqtt_publish(TOPIC_SIGNAL_RSSI, str(rssi))
    mqtt_publish(TOPIC_SIGNAL_QUALITY, signal.get("quality", "unknown"))
    last_signal_publish = now


def handle_lte_network_publish() -> None:
    """Publish LTE network info if LTE is connected."""
    global last_network_publish

    now = time.ticks_ms()
    if time.ticks_diff(now, last_network_publish) < NETWORK_INFO_UPDATE_INTERVAL_MS:
        return

    if not LTE_AVAILABLE or not is_lte_connected():
        return

    network = get_network_info()
    mqtt_publish(TOPIC_NETWORK_OPERATOR, network.get("operator", ""))
    mqtt_publish(TOPIC_NETWORK_TYPE, network.get("type", ""))
    last_network_publish = now


def handle_gps_publish() -> None:
    """Publish GPS location. Polls GPS directly (single-threaded UART)."""
    global last_gps_publish, _last_gps_fix

    if not _gps_available or not ENABLE_GPS:
        return

    now = time.ticks_ms()
    interval = GPS_UPDATE_INTERVAL_MS

    if time.ticks_diff(now, last_gps_publish) >= interval:
        # Poll GPS with timeout
        gps = get_gps_location()

        # Cache last valid fix so we can republish even if GPS temporarily loses signal
        if gps and gps.get("latitude", 0) != 0 and gps.get("longitude", 0) != 0:
            _last_gps_fix = gps

        # Publish from latest known fix
        data = _last_gps_fix
        if data:
            # Bundle all GPS data into one JSON message
            gps_payload = ujson.dumps(
                {
                    "latitude": data.get("latitude", 0),
                    "longitude": data.get("longitude", 0),
                    "altitude": data.get("altitude", 0),
                    "speed": data.get("speed", 0),
                }
            )
            mqtt_publish(TOPIC_DEVICE_TRACKER, gps_payload, retain=True)
        last_gps_publish = now


def run_main_loop() -> None:
    """Run the main MQTT loop.

    Optimized: calls check_msg() only twice per iteration (start + end)
    instead of after every single operation. Incoming messages are buffered
    by the SIM7600 and processed at the next check.
    """
    global mqtt_client

    try:
        # Check for incoming messages first (highest priority)
        handle_mqtt_message()

        # Send all outgoing data without intermediate message checks
        # The SIM7600 buffers incoming data, nothing is lost
        handle_sensor_publish()
        handle_connection_type_publish()
        handle_lte_signal_publish()
        handle_lte_network_publish()
        handle_gps_publish()

        # Final check for any messages that arrived during the publish batch
        handle_mqtt_message()

        time.sleep(MQTT_LOOP_DELAY)

    except OSError as e:
        log("WARN", f"Connection lost: {e}")
        blink_pattern("111")
        disconnect_mqtt()
        # OSError(-1) = broker closed connection (peer reset). Wait longer to
        # let the broker expire the old session before reconnecting.
        time.sleep(15.0 if e.args[0] == -1 else ERROR_DELAY_LONG)

    except Exception as e:
        err_str = str(e)
        # Check for SSL-specific errors
        if (
            "-104" in err_str
            or "SSL" in err_str
            or "closed" in err_str.lower()
            or "ECONNRESET" in err_str
        ):
            log("WARN", f"SSL/Connection error: {e}")
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
def try_time_sync() -> bool:
    """Try to sync time via NTP.

    Uses the unified sync_time() function from lte_utils which uses
    NTP via WiFi or LTE connection.

    Returns:
        True if time was synced successfully
    """
    global time_synced

    if time_synced:
        return True

    try:
        # Use the unified sync_time() from lte_utils
        if sync_time():
            time_synced = True
            log("TIME", "Time synced successfully")
            return True
    except Exception as e:
        log("TIME", f"Time sync error: {e}")

    return False


def main() -> None:
    """Main entry point."""
    global last_sensor_publish, mqtt_client, _gps_available, time_synced
    global reconnect_count  # noqa: F821

    # Import sync_time here to avoid circular imports
    from lte_utils import sync_time as do_sync_time

    validate_config()

    log("BOOT", f"Starting Pico 2W MQTT Client - {uid}")

    blink_pattern("11011")

    disconnect_mqtt()

    # Time sync state
    time_synced = False
    time_sync_retry_count = 0
    last_time_sync_retry = 0
    TIME_SYNC_RETRY_INTERVAL_MS = 300000  # Retry every 5 minutes

    while True:
        # Check LTE first, only use WiFi as fallback
        if LTE_AVAILABLE and is_lte_connected():
            # Try to sync time if not yet synced or retry interval passed
            if not time_synced:
                now = time.ticks_ms()
                if (
                    time_sync_retry_count == 0
                    or time.ticks_diff(now, last_time_sync_retry)
                    >= TIME_SYNC_RETRY_INTERVAL_MS
                ):
                    log("TIME", "Attempting time sync...")
                    last_time_sync_retry = now

                    if do_sync_time():
                        time_synced = True
                        time_sync_retry_count = 0
                    else:
                        time_sync_retry_count += 1
                        log(
                            "TIME",
                            f"Time sync failed (attempt {time_sync_retry_count}), "
                            f"will retry in {TIME_SYNC_RETRY_INTERVAL_MS // 1000}s",
                        )
        else:
            # LTE not connected, ensure WiFi
            if not ensure_wifi():
                time.sleep(RECONNECT_DELAY_S)
                continue

        # Initialize GPS if not already done
        # If LTE is connected, use the existing SIM7600 from LTE manager
        # Otherwise, initialize fresh for GPS-only mode
        if LTE_AVAILABLE and not _gps_available:
            try:
                manager = get_lte_manager()
                if manager and manager.sim:
                    # LTE manager exists - use its SIM7600 instance
                    # This way gps_enabled state is preserved
                    sim = manager.sim
                    sim.set_logger(lambda tag, msg: log(tag, msg))
                    if not sim.gps_enabled:
                        sim.enable_gps()
                    _gps_available = True
                    log("GPS", "GPS enabled (reusing LTE module)")
                else:
                    # No LTE manager - initialize fresh (WiFi-only mode)
                    init_gps(
                        uart_id=LTE_UART_ID,
                        tx_pin=LTE_TX_PIN,
                        rx_pin=LTE_RX_PIN,
                        baudrate=LTE_BAUD,
                        rts_pin=LTE_RTS_PIN,
                        cts_pin=LTE_CTS_PIN,
                    )
                    _gps_available = True
            except Exception as e:
                log("GPS", f"Init failed: {e}")

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
