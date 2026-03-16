"""
main.py - Entry Point for Pico 2W MQTT Client

This is the main entry point that runs on boot. It handles firmware updates
and network connections before launching the main application.

Connection Priority (configurable in config.py):
    1. LTE (SIM7600G-H) - Primary connection
       - Syncs time from GPS on boot (critical for TLS!)
    2. WiFi (Pico W) - Fallback connection

Update Priority:
    1. GitHub updates (if enabled and network available)
    2. Launch main application

Rollback:
    Press the update button twice within 2 seconds at boot to trigger
    a rollback to the previous firmware version.

Usage:
    Upload all .py files to Pico flash. On reset, this file runs first.
    It will check for updates and then launch the application automatically.

Configuration:
    Update behavior is controlled by config.py settings:
    - GITHUB_OWNER, GITHUB_REPO: GitHub repository for updates
    - UPDATE_BUTTON_PIN: GPIO pin for rollback trigger (default: 10)
    - PRIMARY_CONNECTION: "LTE" or "WIFI"
    - FALLBACK_CONNECTION: "WIFI" or "LTE"
    - LTE_ENABLED: Enable/disable LTE
"""

import sys
import machine

from wifi_utils import scan_and_connect
from updater_utils import log, detect_rollback_trigger, perform_rollback

try:
    from config import (
        GITHUB_OWNER,
        GITHUB_REPO,
        UPDATE_BUTTON_PIN,
        LTE_ENABLED,
        LTE_APN,
        LTE_SIM_PIN,
        LTE_UART_ID,
        LTE_TX_PIN,
        LTE_RX_PIN,
        LTE_BAUD,
        LTE_SYNC_TIME_ON_BOOT,
        LTE_CONNECT_TIMEOUT_MS,
        PRIMARY_CONNECTION,
        FALLBACK_CONNECTION,
    )

    GITHUB_UPDATES_ENABLED = True
except Exception:
    GITHUB_UPDATES_ENABLED = False
    LTE_ENABLED = False
    PRIMARY_CONNECTION = "WIFI"
    FALLBACK_CONNECTION = "WIFI"

CONNECTION_TYPE = None
lte_connected = False


def connect_lte() -> bool:
    """Connect to LTE network.

    Returns:
        True if connected
    """
    global lte_connected

    if not LTE_ENABLED:
        return False

    try:
        from lte_utils import connect_lte as do_connect_lte

        log("LTE", "Attempting LTE connection...")
        if do_connect_lte(
            apn=LTE_APN,
            pin=LTE_SIM_PIN,
            enable_gps=True,
            sync_time=LTE_SYNC_TIME_ON_BOOT,
            timeout_ms=LTE_CONNECT_TIMEOUT_MS,
            uart_id=LTE_UART_ID,
            tx_pin=LTE_TX_PIN,
            rx_pin=LTE_RX_PIN,
            baudrate=LTE_BAUD,
        ):
            lte_connected = True
            return True
    except Exception as e:
        log("LTE", f"Connection failed: {e}")

    return False


def connect_wifi() -> bool:
    """Connect to WiFi network.

    Returns:
        True if connected
    """
    try:
        from config import WIFI_SSID, WIFI_PASSWORD, WIFI_SSID_2, WIFI_PASSWORD_2

        log("WiFi", "Attempting WiFi connection...")
        networks = [(WIFI_SSID, WIFI_PASSWORD)]
        if WIFI_SSID_2 and WIFI_PASSWORD_2:
            networks.append((WIFI_SSID_2, WIFI_PASSWORD_2))

        if scan_and_connect(networks):
            log("WiFi", "WiFi connected!")
            return True

        log("WiFi", "WiFi connection failed")
    except Exception as e:
        log("WiFi", f"Connection failed: {e}")

    return False


def try_primary_connection() -> bool:
    """Try primary connection (LTE or WiFi based on config).

    Returns:
        True if connected
    """
    global CONNECTION_TYPE

    if PRIMARY_CONNECTION == "LTE":
        if connect_lte():
            CONNECTION_TYPE = "LTE"
            return True
        log("LTE", "Primary connection failed, trying fallback...")
        if FALLBACK_CONNECTION == "WIFI":
            if connect_wifi():
                CONNECTION_TYPE = "WiFi"
                return True
    else:
        if connect_wifi():
            CONNECTION_TYPE = "WiFi"
            return True
        log("WiFi", "Primary connection failed, trying fallback...")
        if FALLBACK_CONNECTION == "LTE":
            if connect_lte():
                CONNECTION_TYPE = "LTE"
                return True

    return False


github_updated = False
update_check_executed = False

if GITHUB_UPDATES_ENABLED:
    try:
        if detect_rollback_trigger(UPDATE_BUTTON_PIN):
            log("Rollback triggered!")
            if perform_rollback():
                log("Rebooting...")
                machine.reset()
    except Exception as e:
        log(f"Rollback check failed: {e}")

log(f"Primary: {PRIMARY_CONNECTION}, Fallback: {FALLBACK_CONNECTION}")

if not try_primary_connection():
    log("All connections failed!")

if CONNECTION_TYPE:
    log(f"Connected via: {CONNECTION_TYPE}")

    if GITHUB_UPDATES_ENABLED:
        try:
            from github_updater import check_and_update

            update_check_executed = True
            github_updated = check_and_update(GITHUB_OWNER, GITHUB_REPO)

            if github_updated:
                log("GitHub update applied, rebooting...")
            else:
                log("No GitHub update available")
        except Exception as e:
            log(f"GitHub update check failed: {e}")
else:
    log("No network connection available")

try:
    import app

    app.main()
except Exception as e:
    log(f"Main failed: {e}")
    sys.exit(1)
