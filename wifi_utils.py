"""
WiFi Utilities for Pico 2W
Shared WiFi connection functions
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
