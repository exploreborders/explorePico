"""
WiFi Utilities for Pico 2W

Shared WiFi connection functions for connecting to wireless networks.
Provides both low-level and high-level connection APIs.

Functions:
    get_wlan(): Get the WLAN station interface
    is_connected(): Check if WiFi is connected
    connect(): Connect to WiFi with retry logic
    connect_multi(): Connect to multiple networks (tries in order)

Usage:
    from wifi_utils import connect, is_connected, connect_multi

    # Check connection
    if is_connected():
        print("Connected!")

    # Connect with callbacks
    connect("MyNetwork", "password", log_fn=log, blink_fn=blink)

    # Connect to multiple networks (try home first, then phone)
    connect_multi(networks, log_fn=log, blink_fn=blink)

Notes:
    - Uses network.WLAN(network.STA_IF) for station mode
    - Default timeout is 30 seconds per network
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


def connect(
    ssid: str,
    password: str,
    timeout: int = 30,
    log_fn=None,
    blink_fn=None,
) -> bool:
    """Connect to WiFi. Returns True if connected.

    Args:
        ssid: WiFi network name
        password: WiFi password
        timeout: Connection timeout in seconds
        log_fn: Optional logging function (tag, message) -> None
        blink_fn: Optional blink pattern function (pattern) -> None
    """
    if blink_fn:
        blink_fn("10")

    if log_fn:
        log_fn("WiFi", "Connecting...")

    wlan = get_wlan()
    wlan.active(True)
    wlan.connect(ssid, password)

    for _ in range(timeout):
        if wlan.isconnected():
            if blink_fn:
                blink_fn("1010")
            if log_fn:
                log_fn("WiFi", f"Connected! IP: {wlan.ifconfig()[0]}")
            return True
        time.sleep(1)

    if blink_fn:
        blink_fn("111")
    if log_fn:
        log_fn("WiFi", "Failed to connect")
    return False


def connect_multi(
    networks: list[tuple[str, str]],
    timeout: int = 30,
    log_fn=None,
    blink_fn=None,
) -> bool:
    """Connect to WiFi trying multiple networks in order. Returns True if connected.

    Args:
        networks: List of (ssid, password) tuples to try in order
        timeout: Connection timeout in seconds per network
        log_fn: Optional logging function (tag, message) -> None
        blink_fn: Optional blink pattern function (pattern) -> None

    Returns:
        True if connected to any network, False otherwise
    """
    for i, (ssid, password) in enumerate(networks):
        if log_fn:
            log_fn("WiFi", f"Trying {ssid}...")

        if connect(ssid, password, timeout=timeout, log_fn=log_fn, blink_fn=blink_fn):
            if log_fn:
                log_fn("WiFi", f"Connected to {ssid}")
            return True

        if log_fn:
            log_fn("WiFi", f"Failed to connect to {ssid}")

    if log_fn:
        log_fn("WiFi", "No networks available")
    return False
