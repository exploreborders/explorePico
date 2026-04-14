"""
LTE Utilities for Pico 2W

High-level LTE connection functions using SIM7600G-H module.
Provides time sync (NTP), GPS, signal info, and network monitoring.

Functions:
    init_gps(): Initialize SIM7600 for GPS (no LTE connection)
    connect_lte(): Connect to LTE network
    is_lte_connected(): Check if LTE is connected
    get_gps_location(): Get GPS coordinates
    get_signal_info(): Get signal quality
    get_network_info(): Get network information
    sync_time(): Sync system time from NTP (MAIN ENTRY POINT)

Usage:
    from lte_utils import init_gps, connect_lte, is_lte_connected, sync_time

    init_gps(uart_id=0, tx_pin=0, rx_pin=1)  # GPS works with any connection
    if connect_lte("internet", "5046"):
        print("LTE connected!")
    sync_time()  # Sync time via NTP
    location = get_gps_location()
"""

import time as time_module

from sensors.sim7600 import SIM7600, SIM7600Manager


_lte_manager: SIM7600Manager | None = None
_log_fn = None
_time_synced = False
_time_sync_source = None
_reconnect_attempts = 0
MAX_RECONNECT_ATTEMPTS = 3


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
    rts_pin: int = 2,
    cts_pin: int = 3,
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
        rts_pin: GPIO pin for RTS (hardware flow control)
        cts_pin: GPIO pin for CTS (hardware flow control)

    Returns:
        True if initialized successfully
    """
    global _lte_manager

    _log("GPS", "Initializing SIM7600 for GPS...")

    sim = SIM7600(uart_id, tx_pin, rx_pin, baudrate, rts_pin, cts_pin)
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
    rts_pin: int = 2,
    cts_pin: int = 3,
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
        rts_pin: GPIO pin for RTS (hardware flow control)
        cts_pin: GPIO pin for CTS (hardware flow control)

    Returns:
        True if connected successfully
    """
    global _lte_manager

    # Reset reconnect counter on new connection attempt
    global _reconnect_attempts
    _reconnect_attempts = 0

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

    sim = SIM7600(uart_id, tx_pin, rx_pin, baudrate, rts_pin, cts_pin)
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
    """Get GPS location (single poll, waits for fix up to timeout).

    Args:
        timeout_ms: Maximum wait time for fix (default 2s)

    Returns:
        Dict with lat, lon, alt, speed, course, pdop, hdop, vdop,
        satellites, source or None
    """
    if not _lte_manager:
        return None

    return _lte_manager.get_gps_location(timeout_ms=timeout_ms)


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


def sync_time(force: bool = False) -> bool:
    """Sync system time from GPS (MAIN ENTRY POINT).

    Priority:
    1. GPS time (works with LTE or WiFi)
    2. NTP via WiFi (if connected)

    Args:
        force: Force sync even if already synced

    Returns:
        True if synced successfully
    """
    global _time_synced, _time_sync_source

    if _time_synced and not force:
        _log("TIME", "Already synced (use force=True to resync)")
        return True

    _log("TIME", "Syncing time from GPS...")
    if _sync_time_from_gps():
        _time_synced = True
        _time_sync_source = "GPS"
        _log("TIME", "Time synced via GPS")
        return True

    if is_wifi_connected():
        _log("TIME", "Trying WiFi NTP...")
        if _sync_time_ntp():
            _time_synced = True
            _time_sync_source = "NTP"
            _log("TIME", "Time synced via WiFi NTP")
            return True

    _log("TIME", "Time sync failed - no valid source")
    return False


def _sync_time_from_gps() -> bool:
    """Get time from GPS (AT+CGNSINFO).

    Returns:
        True if time synced successfully
    """
    if not _lte_manager:
        _log("TIME", "No LTE manager for GPS")
        return False

    try:
        sim = _lte_manager.sim
        if not sim:
            _log("TIME", "No SIM7600 instance")
            return False

        gps_time = sim.get_gps_time()
        if not gps_time:
            _log("TIME", "No GPS time available")
            return False

        year, month, day, hour, minute, second = gps_time

        if year < 2020 or year > 2100:
            _log("TIME", f"Invalid GPS time: {year}-{month:02d}-{day:02d}")
            return False

        import machine

        rtc = machine.RTC()
        rtc.datetime((year, month, day, 0, hour, minute, second, 0))
        _log(
            "TIME",
            f"GPS time: {year}-{month:02d}-{day:02d} "
            f"{hour:02d}:{minute:02d}:{second:02d}",
        )
        return True
    except Exception as e:
        _log("TIME", f"GPS time failed: {e}")
    return False


def _sync_time_ntp() -> bool:
    """Internal NTP sync helper (private - use sync_time())."""
    if not _is_network_available():
        _log("TIME", "No network connection for NTP sync")
        return False

    # Try standard NTP — cap socket wait to avoid hanging indefinitely
    import ntptime

    for ntp_host in ("pool.ntp.org", "time.cloudflare.com"):
        try:
            ntptime.host = ntp_host
            ntptime.timeout = 5
            ntptime.settime()

            now = time_module.localtime()
            _log(
                "TIME",
                f"NTP synced via {ntp_host}: {now[0]}-{now[1]:02d}-{now[2]:02d} "
                f"{now[3]:02d}:{now[4]:02d}:{now[5]:02d}",
            )
            return True
        except Exception as e:
            _log("TIME", f"NTP {ntp_host} failed: {e}")

    # Fallback: Try to get time from LTE network (AT+CCLK)
    return _sync_time_from_network()


def _is_network_available() -> bool:
    """Check if any network is available (WiFi or LTE)."""
    # Check WiFi
    try:
        import network

        sta = network.WLAN(network.STA_IF)
        if sta.isconnected():
            return True
    except OSError:
        pass

    # Check LTE
    if _lte_manager and _lte_manager.is_connected():
        return True

    return False


def _sync_time_from_network() -> bool:
    """Fallback: Get time from LTE network via AT+CCLK.

    Returns:
        True if time synced successfully
    """
    if not _lte_manager or not _lte_manager.is_connected():
        _log("TIME", "No LTE for network time")
        return False

    try:
        sim = _lte_manager.sim
        if sim:
            network_time = sim.get_network_time()
            if network_time:
                _log("TIME", f"Network time: {network_time}")
                return True
    except Exception as e:
        _log("TIME", f"Network time failed: {e}")
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
    except OSError:
        return False


def is_time_synced() -> bool:
    """Check if time has been synced."""
    global _time_synced
    return _time_synced


def get_time_sync_source() -> str | None:
    """Get the source of last time sync (NTP or None)."""
    global _time_sync_source
    return _time_sync_source


def reconnect_if_needed() -> bool:
    """Reconnect to LTE if not connected.

    Uses a lightweight reconnect that doesn't restart the modem.
    Only reopens the network service and PDP context.
    Has a maximum retry limit to prevent infinite loops.

    Returns:
        True if connected or reconnected
    """
    global _lte_manager, _reconnect_attempts

    if is_lte_connected():
        _reconnect_attempts = 0  # Reset on successful connection
        return True

    if _reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
        _log("LTE", f"Max reconnect attempts ({MAX_RECONNECT_ATTEMPTS}) reached")
        return False

    if not _lte_manager or not _lte_manager.sim:
        return False

    _reconnect_attempts += 1
    _log("LTE", f"Reconnect attempt {_reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS}")

    sim = _lte_manager.sim

    # Check if modem is still responsive
    resp = sim.send_at("AT", timeout=2000)
    if "OK" not in resp:
        _log("LTE", "Modem not responsive, full reconnect needed")
        return False

    _log("LTE", "Reconnecting data session...")

    # Close and reopen network service
    sim.send_at("AT+NETCLOSE", timeout=5000)
    time_module.sleep(1)

    # Reactivate PDP
    if not sim.activate_pdp():
        _log("LTE", "PDP reactivation failed")
        return False

    # Reopen network service
    if not sim.open_network():
        _log("LTE", "Network reopen failed")
        return False

    # Wait for IP
    ip = sim.get_ip_address()
    if ip:
        _log("LTE", f"Reconnected with IP: {ip}")
        sim.lte_connected = True
        _reconnect_attempts = 0  # Reset on success
        return True

    _log("LTE", "Reconnection failed - no IP")
    return False
