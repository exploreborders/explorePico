"""
LTE Utilities for Pico 2W

High-level LTE connection functions using SIM7600G-H module.
Provides time sync, GPS, signal info, and network monitoring.

Functions:
    connect_lte(): Initialize and connect to LTE network
    is_lte_connected(): Check if LTE is connected
    get_gps_location(): Get GPS coordinates
    get_signal_info(): Get signal quality
    get_network_info(): Get network information
    sync_time(): Sync system time from GPS

Usage:
    from lte_utils import connect_lte, is_lte_connected

    if connect_lte("internet", "5046"):
        print("LTE connected!")
"""

from sensors.sim7600 import SIM7600, SIM7600Manager


_lte_manager: SIM7600Manager | None = None
_log_fn = None


def set_logger(log_fn) -> None:
    """Set logging function.

    Args:
        log_fn: Function that takes (tag, message)
    """
    global _log_fn
    _log_fn = log_fn


def _log(tag: str, message: str) -> None:
    """Log message using configured logger."""
    if _log_fn:
        _log_fn(tag, message)
    else:
        print(f"[{tag}] {message}")


def init_lte(
    uart_id: int = 0,
    tx_pin: int = 1,
    rx_pin: int = 0,
    baudrate: int = 115200,
) -> SIM7600 | None:
    """Initialize SIM7600 module.

    Args:
        uart_id: UART peripheral (0 or 1)
        tx_pin: GPIO pin for TX
        rx_pin: GPIO pin for RX
        baudrate: UART baudrate

    Returns:
        SIM7600 instance or None on failure
    """
    global _lte_manager

    sim = SIM7600(uart_id, tx_pin, rx_pin, baudrate)
    sim.set_logger(_log)

    if sim.init():
        return sim

    return None


def connect_lte(
    apn: str,
    pin: str | None = None,
    enable_gps: bool = True,
    sync_time: bool = False,
    timeout_ms: int = 90000,
    uart_id: int = 0,
    tx_pin: int = 1,
    rx_pin: int = 0,
    baudrate: int = 115200,
) -> bool:
    """Connect to LTE network with optional GPS and time sync.

    This function:
    1. Initializes SIM7600
    2. Enables GPS and syncs time (critical for TLS!)
    3. Connects to LTE network

    Args:
        apn: Access Point Name (e.g., "internet")
        pin: SIM PIN code (optional)
        enable_gps: Enable GPS for location tracking
        sync_time: Sync time from GPS (recommended for TLS)
        timeout_ms: Connection timeout in ms
        uart_id: UART peripheral
        tx_pin: TX GPIO pin
        rx_pin: RX GPIO pin
        baudrate: UART baudrate

    Returns:
        True if connected successfully
    """
    global _lte_manager

    _log("LTE", "Initializing SIM7600...")

    sim = SIM7600(uart_id, tx_pin, rx_pin, baudrate)
    sim.set_logger(_log)

    if not sim.init():
        _log("LTE", "SIM7600 init failed")
        return False

    if sync_time:
        # Only require time sync if SSL is enabled (needed for certificate validation)
        from config import MQTT_SSL

        if MQTT_SSL:
            # Try NTP first (fast, < 1 second)
            _log("LTE", "SSL enabled, syncing time via NTP (fast)...")
            if sync_time_ntp():
                _log("LTE", "NTP time sync succeeded!")
            else:
                # NTP failed, try GPS as fallback but don't block
                _log("LTE", "NTP failed, trying GPS...")
                sim.enable_gps()
                if not sim.sync_time_from_gps(timeout_ms=10000):
                    _log("LTE", "GPS time sync timeout, continuing anyway...")
                _log("LTE", "Time sync will retry in main loop")
        else:
            _log("LTE", "Non-SSL MQTT, skipping time sync")

    _log("LTE", f"Connecting to LTE (APN: {apn})...")

    if not sim.connect_lte(apn, pin, timeout_ms):
        _log("LTE", "LTE connection failed")
        return False

    _lte_manager = SIM7600Manager(sim, apn, pin)
    _lte_manager.set_logger(_log)

    if enable_gps:
        sim.enable_gps()

    return True


def is_lte_connected() -> bool:
    """Check if LTE is connected.

    Returns:
        True if connected
    """
    if _lte_manager:
        return _lte_manager.is_connected()
    return False


def get_lte_manager() -> SIM7600Manager | None:
    """Get LTE manager instance.

    Returns:
        SIM7600Manager or None
    """
    return _lte_manager


def get_lte_ip_address() -> str | None:
    """Get the LTE IP address.

    Returns:
        IP address string or None
    """
    if not _lte_manager:
        return None
    return _lte_manager.get_ip_address()


def get_gps_location(timeout_ms: int = 30000) -> dict | None:
    """Get GPS location.

    Args:
        timeout_ms: Maximum wait time for fix

    Returns:
        Dict with lat, lon, alt, speed, satellites or None
    """
    if not _lte_manager:
        return None

    return _lte_manager.get_gps_location()


def get_signal_info() -> dict:
    """Get signal quality information.

    Returns:
        Dict with rssi (dBm) and quality (text)
    """
    if not _lte_manager:
        return {"rssi": 0, "quality": "unknown"}

    return _lte_manager.get_signal_info()


def get_network_info() -> dict:
    """Get network information.

    Returns:
        Dict with operator, type, registered
    """
    if not _lte_manager:
        return {
            "operator": "",
            "type": "",
            "registered": False,
        }

    return _lte_manager.get_network_info()


def sync_time_ntp() -> bool:
    """Sync system time from NTP server (fast, internet-based).

    Returns:
        True if synced successfully
    """
    if not is_lte_connected() and not is_wifi_connected():
        _log("TIME", "No network connection for NTP sync")
        return False

    try:
        import ntptime

        ntptime.host = "pool.ntp.org"
        ntptime.settime()

        import time

        now = time.localtime()
        _log(
            "TIME",
            f"NTP time synced: {now[0]}-{now[1]:02d}-{now[2]:02d} {now[3]:02d}:{now[4]:02d}:{now[5]:02d}",
        )
        return True
    except Exception as e:
        _log("TIME", f"NTP sync failed: {e}")
        return False


def is_wifi_connected() -> bool:
    """Check if WiFi is connected.

    Returns:
        True if WiFi is connected
    """
    try:
        import network

        sta = network.WLAN(network.STA_IF)
        return sta.isconnected()
    except:
        return False


def sync_time() -> bool:
    """Sync system time - tries NTP first (fast), then GPS (fallback).

    Returns:
        True if synced via any method
    """
    # Try NTP first (fast, takes < 1 second)
    _log("TIME", "Trying NTP sync (fast)...")
    if sync_time_ntp():
        return True

    # Fall back to GPS if NTP fails
    _log("TIME", "NTP failed, trying GPS...")
    if not _lte_manager:
        _log("TIME", "No LTE manager for GPS sync")
        return False

    return _lte_manager.sync_time()


def reconnect_if_needed() -> bool:
    """Reconnect to LTE if not connected.

    Returns:
        True if connected or reconnected
    """
    global _lte_manager

    if is_lte_connected():
        return True

    if not _lte_manager:
        return False

    _log("LTE", "Reconnecting...")

    if _lte_manager.connect():
        _log("LTE", "Reconnected")
        return True

    _log("LTE", "Reconnection failed")
    return False
