"""
WiFi Utilities for Pico 2W

Shared WiFi connection functions for connecting to wireless networks.
Provides both low-level and high-level connection APIs.

Functions:
    get_wlan(): Get the WLAN station interface
    is_connected(): Check if WiFi is connected
    scan_and_connect(): Scan and connect to first available network

Usage:
    from wifi_utils import scan_and_connect, is_connected

    # Check connection
    if is_connected():
        print("Connected!")

    # Scan for networks and connect to first available
    networks = [("MyNetwork", "password"), ("BackupNetwork", "password2")]
    scan_and_connect(networks, log_fn=log, blink_fn=blink)

Notes:
    - Uses network.WLAN(network.STA_IF) for station mode
    - Default timeout is 10 seconds
    - Optional log_fn and blink_fn for feedback
"""

import network
import time


def get_wlan():
    """Get WLAN station interface."""
    return network.WLAN(network.STA_IF)


def is_connected() -> bool:
    """Check if WiFi is connected."""
    wlan = get_wlan()
    return wlan.isconnected()


def scan_and_connect(
    networks: list[tuple[str, str]],
    timeout: int = 10,
    log_fn=None,
    blink_fn=None,
) -> bool:
    """Scan for available networks and connect to first available. Returns True if connected.

    Args:
        networks: List of (ssid, password) tuples to check
        timeout: Connection timeout in seconds
        log_fn: Optional logging function (tag, message) -> None
        blink_fn: Optional blink pattern function (pattern) -> None

    Returns:
        True if connected to any network, False otherwise
    """
    if blink_fn:
        blink_fn("10")

    if log_fn:
        log_fn("WiFi", "Scanning for networks...")

    wlan = get_wlan()
    wlan.active(True)

    # Scan for networks
    scan_results = wlan.scan()

    # Extract available SSIDs
    available_ssids = {result[0].decode("utf-8") for result in scan_results}

    if log_fn:
        log_fn("WiFi", f"Found {len(available_ssids)} networks")

    # Find first configured network that's available
    for ssid, password in networks:
        if ssid in available_ssids:
            if log_fn:
                log_fn("WiFi", f"Found {ssid}, connecting...")

            # Connect to the network
            wlan.connect(ssid, password)

            for _ in range(timeout):
                if wlan.isconnected():
                    if blink_fn:
                        blink_fn("1010")
                    if log_fn:
                        log_fn("WiFi", f"Connected! IP: {wlan.ifconfig()[0]}")
                    return True
                time.sleep(1)

            if log_fn:
                log_fn("WiFi", f"Failed to connect to {ssid}")

    if log_fn:
        log_fn("WiFi", "No configured networks found")

    if blink_fn:
        blink_fn("111")
    return False
