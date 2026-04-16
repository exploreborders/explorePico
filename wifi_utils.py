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
    try:
        wlan = get_wlan()
        return wlan.isconnected()
    except OSError:
        return False


def scan_and_connect(
    networks: list[tuple[str, str]],
    timeout: int = 10,
    log_fn=None,
    blink_fn=None,
) -> bool:
    """Scan for available networks and connect to first available.

    Returns True if connected.

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

    try:
        return _scan_and_connect_impl(networks, timeout, log_fn, blink_fn)
    except Exception as e:
        if log_fn:
            log_fn("WiFi", f"Scan failed: {e}")
        if blink_fn:
            blink_fn("111")
        return False


def _scan_and_connect_impl(
    networks: list[tuple[str, str]],
    timeout: int = 10,
    log_fn=None,
    blink_fn=None,
) -> bool:
    if log_fn:
        log_fn("WiFi", "Scanning for networks...")

    wlan = get_wlan()

    # Deactivate and reactivate WiFi to ensure clean state after soft reset
    # Also disconnect first to clear any previous connection state
    try:
        wlan.disconnect()
    except OSError:
        pass
    time.sleep(0.5)

    try:
        wlan.active(False)
        time.sleep(0.5)
        wlan.active(True)
    except OSError:
        pass

    # Wait for radio to be ready
    time.sleep(2)

    # Retry scan — CYW43 radio can take a few seconds to be ready
    scan_results = []
    scan_start = time.ticks_ms()
    scan_timeout_ms = 10000  # 10 seconds max for scanning

    for _ in range(3):
        if time.ticks_diff(time.ticks_ms(), scan_start) > scan_timeout_ms:
            if log_fn:
                log_fn("WiFi", "Scan timeout reached")
            break
        time.sleep(1)
        try:
            results = wlan.scan()
            # Validate entire results structure first
            if not isinstance(results, list):
                if log_fn:
                    log_fn("WiFi", f"Scan returned unexpected type: {type(results)}")
                continue
            # Validate each result individually
            for r in results:
                if not isinstance(r, (tuple, list)):
                    continue
                if len(r) < 1:
                    continue
                scan_results.append(r)
            if scan_results:
                break
        except OSError as e:
            if log_fn:
                log_fn("WiFi", f"Scan error: {e}")
        except Exception as e:
            if log_fn:
                log_fn("WiFi", f"Scan exception: {e}")

    # Extract available SSIDs, skip any that can't be decoded or are corrupted
    available_ssids = set()
    if not isinstance(scan_results, list):
        scan_results = []

    for result in scan_results:
        try:
            # Each result should be a tuple with at least 1 element (ssid)
            if not isinstance(result, (tuple, list)):
                continue
            if len(result) < 1:
                continue
            ssid = result[0]
            if not isinstance(ssid, bytes):
                continue
            available_ssids.add(ssid.decode("utf-8"))
        except (UnicodeError, IndexError, OSError, TypeError):
            pass

    if log_fn:
        log_fn("WiFi", f"Found {len(available_ssids)} networks")

    # Find first configured network that's available
    for ssid, password in networks:
        try:
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
                            try:
                                ip = wlan.ifconfig()[0]
                            except (OSError, IndexError):
                                ip = "unknown"
                            log_fn("WiFi", f"Connected! IP: {ip}")
                        return True
                    time.sleep(1)

                if log_fn:
                    log_fn("WiFi", f"Failed to connect to {ssid}")
        except Exception as e:
            if log_fn:
                log_fn("WiFi", f"Connection error: {e}")

    if log_fn:
        log_fn("WiFi", "No configured networks found")

    if blink_fn:
        blink_fn("111")
    return False
