"""
Boot Process Diagnostic Test for Pico 2W MQTT Client
Tests each step of the boot process with detailed logging
"""

import time
import machine
from machine import Pin, ADC, UART, I2C
import onewire
import ds18x20

# Import our modules
from blink import blink_pattern, led
from wifi_utils import scan_and_connect, is_connected
from lte_utils import (
    init_lte,
    connect_lte,
    is_lte_connected,
    get_gps_location,
    get_signal_info,
    get_network_info,
    sync_time,
)
from updater_utils import log, set_logger, read_version
from config import *
from sensors import DS18B20, DS18B20Manager
from sensors.ads1115 import ADS1115
from sensors.acs37030 import ACS37030


def set_test_logger():
    """Set up logger for tests"""

    def test_logger(tag, message):
        timestamp = time.ticks_ms()
        print(f"[TEST-{timestamp}] [{tag}] {message}")

    set_logger(test_logger)


def test_step(step_name, test_func):
    """Run a test step with error handling"""
    log("TEST", f"=== STARTING: {step_name} ===")
    try:
        result = test_func()
        log("TEST", f"=== COMPLETED: {step_name} - Result: {result} ===")
        return result
    except Exception as e:
        log("TEST", f"=== FAILED: {step_name} - Error: {e} ===")
        import sys

        sys.print_exception(e)
        return False


def test_logging():
    """Test logging system"""
    log("LOG", "Logging system test")
    return True


def test_led():
    """Test LED functionality"""
    log("LED", "Testing LED")
    led.on()
    time.sleep(0.5)
    led.off()
    time.sleep(0.5)
    blink_pattern("101")
    return True


def test_button():
    """Test button if available"""
    # Not implemented in current code, but placeholder
    log("BUTTON", "Button test skipped (not implemented)")
    return True


def test_internal_temp():
    """Test internal temperature sensor"""
    log("TEMP", "Testing internal temperature sensor")
    temp_sensor = machine.ADC(INTERNAL_TEMP_ADC_PIN)
    reading = temp_sensor.read_u16()
    voltage = reading * 3.3 / 65535
    temp_c = 27 - (voltage - 0.706) / 0.001721
    log("TEMP", f"Internal temp: {temp_c:.1f}C")
    return True


def test_ds18b20():
    """Test DS18B20 sensors"""
    log("DS18B20", "Testing DS18B20 sensors")
    try:
        ds_pin = machine.Pin(DS18B20_PIN)
        ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
        roms = ds_sensor.scan()
        log("DS18B20", f"Found {len(roms)} DS18B20 devices")
        if roms:
            ds_sensor.convert_temp()
            time.sleep_ms(750)
            for rom in roms:
                temp = ds_sensor.read_temp(rom)
                log("DS18B20", f"Sensor {rom.hex()}: {temp:.1f}C")
        return len(roms) > 0
    except Exception as e:
        log("DS18B20", f"Error: {e}")
        return False


def test_ads1115():
    """Test ADS1115 ADC"""
    log("ADS1115", "Testing ADS1115")
    try:
        ads = ADS1115(
            address=ACS37030_I2C_ADDRESS,
            scl_pin=ACS37030_I2C_SCL_PIN,
            sda_pin=ACS37030_I2C_SDA_PIN,
            i2c_id=ACS37030_I2C_ID,
        )
        if ads.init():
            log("ADS1115", "ADS1115 initialized successfully")
            # Read a channel voltage
            voltage = ads.read_voltage(0)
            if voltage is not None:
                log("ADS1115", f"Channel 0 voltage: {voltage:.3f}V")
            else:
                log("ADS1115", "Failed to read voltage from channel 0")
            # Also test raw reading
            raw = ads.read_raw(0)
            log("ADS1115", f"Channel 0 raw value: {raw}")
            return True
        else:
            log("ADS1115", "Failed to initialize ADS1115")
            return False
    except Exception as e:
        log("ADS1115", f"Error: {e}")
        import sys

        sys.print_exception(e)
        return False


def test_acs37030():
    """Test ACS37030 current sensors"""
    log("ACS37030", "Testing ACS37030 sensors")
    try:
        if not ENABLE_ACS37030:
            log("ACS37030", "ACS37030 disabled in config")
            return True

        # Initialize ADS1115 first
        ads = ADS1115(
            address=ACS37030_I2C_ADDRESS,
            scl_pin=ACS37030_I2C_SCL_PIN,
            sda_pin=ACS37030_I2C_SDA_PIN,
            i2c_id=ACS37030_I2C_ID,
        )

        if not ads.init():
            log("ACS37030", "ADS1115 init failed, cannot test ACS37030")
            return False

        log("ACS37030", "ADS1115 initialized, testing ACS37030 sensors...")

        # Test up to 4 ACS37030 sensors (channels 0-3)
        sensors_tested = 0
        for channel in range(min(ACS37030_NUM_SENSORS, 4)):
            try:
                sensor = ACS37030(
                    ads,
                    channel=channel,
                    sensitivity=ACS37030_SENSITIVITY,
                    zero_point=ACS37030_ZERO_POINT,
                    zero_point_offset=ACS37030_ZERO_OFFSET,
                    is_pico_adc=False,
                )

                # Test direct voltage reading
                voltage = sensor.read_voltage()
                if voltage is not None:
                    log("ACS37030", f"Sensor {channel + 1} - Voltage: {voltage:.3f}V")

                    # Test current calculation
                    current = sensor.read_current()
                    if current is not None:
                        log(
                            "ACS37030",
                            f"Sensor {channel + 1} - Current: {current:.2f}A",
                        )
                        sensors_tested += 1
                    else:
                        log(
                            "ACS37030", f"Sensor {channel + 1} - Failed to read current"
                        )
                else:
                    log("ACS37030", f"Sensor {channel + 1} - No voltage reading")

            except Exception as e:
                log("ACS37030", f"Sensor {channel + 1} - Error: {e}")

        # Test 5th sensor if enabled (uses Pico ADC)
        if ACS37030_NUM_SENSORS >= 5 and ENABLE_ACS37030_PICO_ADC:
            try:
                pico_adc = machine.ADC(ACS37030_PICO_ADC_PIN)
                sensor = ACS37030(
                    pico_adc,
                    channel=0,
                    sensitivity=ACS37030_SENSITIVITY,
                    zero_point=ACS37030_ZERO_POINT,
                    is_pico_adc=True,
                )

                voltage = sensor.read_voltage()
                if voltage is not None:
                    log("ACS37030", f"Sensor 5 (Pico ADC) - Voltage: {voltage:.3f}V")
                    current = sensor.read_current()
                    if current is not None:
                        log(
                            "ACS37030", f"Sensor 5 (Pico ADC) - Current: {current:.2f}A"
                        )
                        sensors_tested += 1
            except Exception as e:
                log("ACS37030", f"Sensor 5 - Error: {e}")

        log("ACS37030", f"Tested {sensors_tested} ACS37030 sensors")
        return sensors_tested > 0

    except Exception as e:
        log("ACS37030", f"Error testing ACS37030: {e}")
        import sys

        sys.print_exception(e)
        return False


def test_config():
    """Test configuration loading"""
    log("CONFIG", "Testing configuration")
    try:
        validate_config()
        log("CONFIG", "Configuration validated successfully")
        log("CONFIG", f"MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
        log("CONFIG", f"MQTT SSL: {MQTT_SSL}")
        log("CONFIG", f"Device Name: {DEVICE_NAME}")
        return True
    except Exception as e:
        log("CONFIG", f"Configuration error: {e}")
        return False


def test_lte_hardware():
    """Test LTE hardware initialization"""
    log("LTE", "Testing LTE hardware")
    try:
        sim = init_lte(
            uart_id=LTE_UART_ID, tx_pin=LTE_TX_PIN, rx_pin=LTE_RX_PIN, baudrate=LTE_BAUD
        )
        if sim:
            log("LTE", "LTE hardware initialized successfully")
            # Test basic AT command
            response = sim.send_at("AT", timeout=1000)
            log("LTE", f"AT response: {response}")
            return "OK" in response
        else:
            log("LTE", "Failed to initialize LTE hardware")
            return False
    except Exception as e:
        log("LTE", f"LTE hardware error: {e}")
        return False


def test_lte_connection():
    """Test LTE connection (full test with GPS time sync)"""
    log("LTE-CONN", "Testing LTE connection (with GPS time sync)")
    return test_lte_connection_full(skip_gps_sync=False)


def test_lte_no_gps():
    """Test LTE connection without GPS time sync (fallback mode)"""
    log("LTE-CONN", "Testing LTE connection (no GPS sync - fallback mode)")
    return test_lte_connection_full(skip_gps_sync=True)


def test_lte_connection_full(skip_gps_sync=False):
    """Test LTE connection

    Args:
        skip_gps_sync: If True, skip GPS time sync to test LTE only
    """
    log("LTE-CONN", "Testing LTE connection")
    try:
        # Import time module for retry logic
        import time

        # Try to connect, optionally skipping GPS time sync
        if skip_gps_sync:
            log("LTE-CONN", "Skipping GPS time sync (LTE only mode)")
            # Initialize LTE without time sync
            sim = init_lte(
                uart_id=LTE_UART_ID,
                tx_pin=LTE_TX_PIN,
                rx_pin=LTE_RX_PIN,
                baudrate=LTE_BAUD,
            )
            if not sim:
                log("LTE-CONN", "Failed to initialize LTE hardware")
                return False

            # Try to enable GPS but don't require time sync
            sim.enable_gps()

            # Try LTE connection with retries
            max_attempts = 2
            for attempt in range(max_attempts):
                log("LTE-CONN", f"LTE connection attempt {attempt + 1}/{max_attempts}")
                if sim.connect_lte(LTE_APN, LTE_SIM_PIN, timeout_ms=60000):
                    log("LTE-CONN", "LTE connected successfully")
                    if is_lte_connected():
                        log("LTE-CONN", "LTE reports as connected")
                        return True
                time.sleep(2)

            log("LTE-CONN", "Failed to connect to LTE after retries")
            return False
        else:
            # Original behavior with GPS time sync
            result = connect_lte(
                apn=LTE_APN,
                pin=LTE_SIM_PIN,
                enable_gps=ENABLE_GPS,
                sync_time=LTE_SYNC_TIME_ON_BOOT,
                timeout_ms=LTE_CONNECT_TIMEOUT_MS,
                uart_id=LTE_UART_ID,
                tx_pin=LTE_TX_PIN,
                rx_pin=LTE_RX_PIN,
                baudrate=LTE_BAUD,
            )
            if result:
                log("LTE-CONN", "LTE connected successfully")
                # Test connection status
                if is_lte_connected():
                    log("LTE-CONN", "LTE reports as connected")
                else:
                    log(
                        "LTE-CONN",
                        "LTE connected but is_lte_connected() returned False",
                    )
                return True
            else:
                log("LTE-CONN", "Failed to connect to LTE")
                return False
    except Exception as e:
        log("LTE-CONN", f"LTE connection error: {e}")
        import sys

        sys.print_exception(e)
        return False


def test_gps():
    """Test GPS functionality"""
    log("GPS", "Testing GPS")
    try:
        if not is_lte_connected():
            log("GPS", "LTE not connected, skipping GPS test")
            return False

        log("GPS", "Getting GPS location...")
        gps_data = get_gps_location(timeout_ms=30000)
        if gps_data:
            log("GPS", f"GPS fix obtained: {gps_data}")
            return True
        else:
            log("GPS", "No GPS fix available")
            return False
    except Exception as e:
        log("GPS", f"GPS test error: {e}")
        return False


def test_time_sync():
    """Test time synchronization"""
    log("TIME", "Testing time sync")
    try:
        if not is_lte_connected():
            log("TIME", "LTE not connected, skipping time sync test")
            return False

        log("TIME", "Syncing time from GPS...")
        result = sync_time()
        if result:
            log("TIME", "Time synchronized successfully")
            # Show current time
            now = time.localtime()
            log(
                "TIME",
                f"Current time: {now[0]:04d}-{now[1]:02d}-{now[2]:02d} {now[3]:02d}:{now[4]:02d}:{now[5]:02d}",
            )
            return True
        else:
            log("TIME", "Failed to sync time")
            return False
    except Exception as e:
        log("TIME", f"Time sync error: {e}")
        return False


def test_wifi():
    """Test WiFi connection"""
    log("WIFI", "Testing WiFi")
    try:
        # Only test if LTE is not connected or as fallback
        if is_lte_connected():
            log("WIFI", "LTE connected, skipping WiFi test (LTE is primary)")
            return True

        log("WIFI", "Attempting WiFi connection...")
        networks = [(WIFI_SSID, WIFI_PASSWORD)]
        if WIFI_SSID_2 and WIFI_PASSWORD_2:
            networks.append((WIFI_SSID_2, WIFI_PASSWORD_2))

        # Log what we're looking for
        configured_ssids = [ssid for ssid, _ in networks]
        log("WIFI", f"Looking for networks: {configured_ssids}")

        result = scan_and_connect(networks, log_fn=log, blink_fn=blink_pattern)
        if result:
            log("WIFI", "WiFi connected successfully")
            if is_connected():
                log("WIFI", "WiFi reports as connected")
            else:
                log("WIFI", "WiFi connected but is_connected() returned False")
            return True
        else:
            log("WIFI", "Failed to connect to WiFi")
            return False
    except Exception as e:
        log("WIFI", f"WiFi error: {e}")
        import sys

        sys.print_exception(e)
        return False


def test_mqtt():
    """Test MQTT connection"""
    log("MQTT", "Testing MQTT connection")
    try:
        from umqtt.simple import MQTTClient

        # Only test if we have network connectivity
        if not (is_lte_connected() or is_connected()):
            log("MQTT", "No network connection, skipping MQTT test")
            return False

        log("MQTT", f"Connecting to {MQTT_BROKER}:{MQTT_PORT}")
        client = MQTTClient(
            client_id=f"test_{machine.unique_id().hex()}",
            server=MQTT_BROKER,
            port=MQTT_PORT,
            user=MQTT_USER,
            password=MQTT_PASSWORD,
            keepalive=30,
            ssl=MQTT_SSL,
        )

        client.connect()
        log("MQTT", "MQTT connected successfully")

        # Test publish
        client.publish("homeassistant/pico/test", "test_message")
        log("MQTT", "Test message published")

        client.disconnect()
        log("MQTT", "MQTT disconnected")
        return True
    except Exception as e:
        log("MQTT", f"MQTT error: {e}")
        try:
            client.disconnect()
        except:
            pass
        return False


def main_test():
    """Run all diagnostic tests"""
    log("TEST", "=== STARTING BOOT PROCESS DIAGNOSTIC ===")
    set_test_logger()

    tests = [
        ("Logging System", test_logging),
        ("LED", test_led),
        ("Button", test_button),
        ("Internal Temperature", test_internal_temp),
        ("Configuration", test_config),
        ("DS18B20 Sensors", test_ds18b20),
        ("ADS1115 ADC", test_ads1115),
        ("ACS37030 Current Sensors", test_acs37030),
        ("LTE Hardware", test_lte_hardware),
        ("LTE Connection (with GPS)", test_lte_connection),
        ("LTE Connection (no GPS)", test_lte_no_gps),
        ("GPS", test_gps),
        ("Time Sync", test_time_sync),
        ("WiFi", test_wifi),
        ("MQTT", test_mqtt),
    ]

    results = {}
    for test_name, test_func in tests:
        results[test_name] = test_step(test_name, test_func)
        time.sleep(1)  # Brief pause between tests

    # Summary
    log("TEST", "=== TEST SUMMARY ===")
    passed = 0
    total = len(tests)
    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        log("TEST", f"{test_name}: {status}")
        if result:
            passed += 1

    log("TEST", f"=== RESULTS: {passed}/{total} tests passed ===")

    if passed == total:
        log("TEST", "All tests passed! System appears to be working correctly.")
        blink_pattern("101010")  # Success pattern
    else:
        log("TEST", "Some tests failed. Check logs above for details.")
        blink_pattern("111")  # Error pattern

    return results


if __name__ == "__main__":
    main_test()
