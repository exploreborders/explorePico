"""
LTE Utilities for Pico 2W

High-level LTE connection functions using SIM7600G-H module.
Provides time sync, GPS, signal info, and network monitoring.

Functions:
    init_gps(): Initialize SIM7600 for GPS (no LTE connection)
    connect_lte(): Connect to LTE network
    is_lte_connected(): Check if LTE is connected
    get_gps_location(): Get GPS coordinates
    get_signal_info(): Get signal quality
    get_network_info(): Get network information
    sync_time(): Sync system time from NTP

Usage:
    from lte_utils import init_gps, connect_lte, is_lte_connected

    init_gps(uart_id=0, tx_pin=0, rx_pin=1)  # GPS works with any connection
    if connect_lte("internet", "5046"):
        print("LTE connected!")
    location = get_gps_location()
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


def init_gps(
    uart_id: int = 0,
    tx_pin: int = 0,
    rx_pin: int = 1,
    baudrate: int = 115200,
) -> bool:
    """Initialize SIM7600 for GPS only (no LTE connection).

    Boots the SIM7600 and enables GPS.
    Works with any network connection (WiFi or LTE).
    Time sync (NTP) is handled separately in app.py after MQTT connects.

    Args:
        uart_id: UART peripheral (0 or 1)
        tx_pin: GPIO pin for TX (GP0)
        rx_pin: GPIO pin for RX (GP1)
        baudrate: UART baudrate

    Returns:
        True if initialized successfully
    """
    global _lte_manager

    _log("GPS", "Initializing SIM7600 for GPS...")

    sim = SIM7600(uart_id, tx_pin, rx_pin, baudrate)
    sim.set_logger(_log)

    if not sim.init():
        _log("GPS", "SIM7600 init failed")
        return False

    _lte_manager = SIM7600Manager(sim, "", "")
    _lte_manager.set_logger(_log)

    sim.enable_gps()

    _log("GPS", "GPS initialized")
    return True


def connect_lte(
    apn: str,
    pin: str | None = None,
    timeout_ms: int = 90000,
    uart_id: int = 0,
    tx_pin: int = 0,
    rx_pin: int = 1,
    baudrate: int = 115200,
) -> bool:
    """Connect to LTE network.

    If _lte_manager already exists (from init_gps), reuses it.
    Otherwise boots the SIM7600 and connects to LTE.

    Args:
        apn: Access Point Name (e.g., "internet")
        pin: SIM PIN code (optional)
        timeout_ms: Connection timeout in ms
        uart_id: UART peripheral
        tx_pin: TX GPIO pin
        rx_pin: RX GPIO pin
        baudrate: UART baudrate

    Returns:
        True if connected successfully
    """
    global _lte_manager

    # Reuse existing SIM7600 if already initialized (e.g., via init_gps)
    if _lte_manager and _lte_manager.sim:
        sim = _lte_manager.sim
        _log("LTE", f"Connecting to LTE (APN: {apn})...")
        if sim.connect_lte(apn, pin, timeout_ms):
            _lte_manager.apn = apn
            _lte_manager.pin = pin
            return True
        _log("LTE", "LTE connection failed")
        return False

    # Fresh init
    _log("LTE", "Initializing SIM7600...")

    sim = SIM7600(uart_id, tx_pin, rx_pin, baudrate)
    sim.set_logger(_log)

    if not sim.init():
        _log("LTE", "SIM7600 init failed")
        return False

    _lte_manager = SIM7600Manager(sim, apn, pin)
    _lte_manager.set_logger(_log)

    _log("LTE", f"Connecting to LTE (APN: {apn})...")

    if not sim.connect_lte(apn, pin, timeout_ms):
        _log("LTE", "LTE connection failed")
        return False

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


def get_gps_location(timeout_ms: int = 2000) -> dict | None:
    """Get GPS location (single poll, non-blocking when fix exists).

    Args:
        timeout_ms: Maximum wait time for fix (default 2s)

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


def sync_time() -> bool:
    """Sync system time from NTP.

    Returns:
        True if synced
    """
    if not _lte_manager:
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
