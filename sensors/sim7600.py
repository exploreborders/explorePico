"""
SIM7600G-H 4G LTE Driver for Pico 2W

Hardware:
    - Module: SIM7600G-H (SIMCom)
    - Interface: UART
    - Features: 4G LTE, GPS

Features:
    - LTE network connection (4G/3G/2G)
    - GPS positioning (GPS/GLONASS/BeiDou/Galileo)
    - Time sync from NTP
    - Signal quality monitoring
    - Network information

AT Commands:
    - Basic: AT, ATI
    - Network: AT+CFUN, AT+CREG, AT+CGREG, AT+COPS
    - GPRS: AT+CGDCONT, AT+CGACT
    - GPS: AT+CGPS, AT+CGPSINFO
    - Signal: AT+CSQ
    - Time: AT+CCLK

Usage:
    from sensors.sim7600 import SIM7600

    sim = SIM7600(uart_id=0, tx_pin=1, rx_pin=0)
    sim.init()
    sim.connect_lte(apn="internet", pin="5046")
    location = sim.get_gps_location()
"""

import time
from machine import UART, Pin


class SIM7600:
    """SIM7600G-H 4G LTE and GPS driver."""

    def __init__(
        self,
        uart_id: int = 0,
        tx_pin: int = 1,
        rx_pin: int = 0,
        baudrate: int = 115200,
    ) -> None:
        """Initialize SIM7600 driver.

        Args:
            uart_id: UART peripheral (0 or 1)
            tx_pin: GPIO pin for UART TX
            rx_pin: GPIO pin for UART RX
            baudrate: UART baudrate (default 115200)
        """
        self.uart_id = uart_id
        self.tx_pin = tx_pin
        self.rx_pin = rx_pin
        self.baudrate = baudrate

        self.uart: UART | None = None
        self._logger = print

        self.gps_enabled = False
        self.gps_configured = False
        self.lte_connected = False

    def set_logger(self, logger) -> None:
        """Set custom logger function."""
        self._logger = logger

    def _log(self, message: str) -> None:
        """Log message using configured logger."""
        self._logger("SIM7600", message)

    def _send_at_simple(self, command: str, timeout: int = 1000) -> str:
        """Simple AT command sender for initialization."""
        if not self.uart:
            return ""

        try:
            while self.uart.any():
                self.uart.read(50)
            time.sleep(0.1)
            self.uart.write(command.encode() + b"\r\n")
            start = time.ticks_ms()
            response = ""

            while time.ticks_diff(time.ticks_ms(), start) < timeout:
                if self.uart.any():
                    data = self.uart.read(256)
                    if data:
                        response += data.decode("utf-8", "ignore")

                if "OK" in response or "ERROR" in response:
                    break

            return response.strip()

        except Exception:
            return ""

    def init(self) -> bool:
        """Initialize UART communication with SIM7600.

        Returns:
            True if SIM7600 responds to AT command
        """
        self._log("Waiting 15s for module to fully boot...")
        time.sleep(15)

        # Initialize UART at fixed 115200
        self.baudrate = 115200
        self._log(f"Connecting at {self.baudrate} baud...")

        try:
            self.uart = UART(
                self.uart_id,
                self.baudrate,
                tx=Pin(self.tx_pin),
                rx=Pin(self.rx_pin),
            )
            self.uart.init(self.baudrate, bits=8, parity=None, stop=1)
        except Exception:
            self._log("Failed to initialize UART")
            return False

        time.sleep(1)

        # Test connection - verify SIM7600 responds
        connected = False
        for attempt in range(5):
            while self.uart.any():
                self.uart.read(100)
            time.sleep(0.5)
            self.uart.write(b"AT\r\n")

            response = ""
            for _ in range(20):
                if self.uart.any():
                    data = self.uart.read(128)
                    if data:
                        response += data.decode("utf-8", "ignore")
                if "OK" in response:
                    connected = True
                    break
                if "ERROR" in response:
                    break
                time.sleep(0.5)

            if connected:
                break

        if not connected:
            self._log("Failed to connect at 115200 baud")
            return False

        self._log("Disabling echo...")
        for _ in range(3):
            resp = self._send_at_simple("ATE0", timeout=2000)
            if resp and "OK" in resp:
                self._log("Echo disabled!")
                break
            time.sleep(0.5)

        self._log("Setting full functionality...")
        for _ in range(3):
            resp = self._send_at_simple("AT+CFUN=1", timeout=3000)
            if resp and "OK" in resp:
                self._log("Full functionality set!")
                break
            time.sleep(1)

        self._log("SIM7600 initialized successfully!")
        return True

    def send_at(
        self,
        command: str,
        timeout: int = 1000,
        expected: str = "OK",
    ) -> str:
        """Send AT command and get response.

        Args:
            command: AT command (without \\r\\n)
            timeout: Timeout in milliseconds
            expected: Expected response keyword

        Returns:
            Response string or "ERROR"
        """
        if not self.uart:
            return "ERROR"

        try:
            while self.uart.any():
                self.uart.read(100)
            time.sleep(0.05)
            self.uart.write(command.encode() + b"\r\n")
            start = time.ticks_ms()
            response = ""

            while time.ticks_diff(time.ticks_ms(), start) < timeout:
                if self.uart.any():
                    char = self.uart.read(1)
                    if char:
                        response += char.decode("utf-8", "ignore")

                if expected in response:
                    return response.strip()

                if "ERROR" in response or "CME ERROR" in response:
                    return "ERROR"

            if response:
                self._log(f"AT response: {response[:100]}")
            return response.strip() if response else "ERROR"

        except Exception as e:
            self._log(f"AT send error: {e}")
            return "ERROR"

    def send_data(self, data: str, timeout: int = 5000) -> str:
        """Send raw data (for MQTT topic/payload input).

        Used after AT commands that expect data input (e.g., AT+CMQTTTOPIC).

        Args:
            data: Data to send
            timeout: Timeout in milliseconds

        Returns:
            Response string
        """
        if not self.uart:
            return "ERROR"

        try:
            self.uart.write(data.encode())
            time.sleep(0.1)
            self.uart.write(b"\r\n")

            start = time.ticks_ms()
            response = ""

            while time.ticks_diff(time.ticks_ms(), start) < timeout:
                if self.uart.any():
                    char = self.uart.read(1)
                    if char:
                        response += char.decode("utf-8", "ignore")

                if "OK" in response:
                    return response.strip()

                if "ERROR" in response:
                    return "ERROR"

            return response.strip() if response else "ERROR"

        except Exception as e:
            self._log(f"Data send error: {e}")
            return "ERROR"

    # -------------------------------------------------------------------------
    # LTE / Network Functions
    # -------------------------------------------------------------------------
    def set_pin(self, pin: str) -> bool:
        """Set SIM PIN.

        Args:
            pin: PIN code as string

        Returns:
            True if successful
        """
        response = self.send_at(f'AT+CPIN="{pin}"', timeout=5000)
        return "OK" in response

    def check_pin(self) -> str:
        """Check SIM PIN status.

        Returns:
            PIN status string (READY, SIM PIN, etc.)
        """
        response = self.send_at("AT+CPIN?")
        if "+CPIN:" in response:
            start = response.find('"') + 1
            end = response.find('"', start)
            if start > 0 and end > start:
                return response[start:end]
        return "UNKNOWN"

    def set_phone_function(self, fun: int = 1) -> bool:
        """Set phone functionality.

        Args:
            fun: 0=minimum, 1=full, 4=airplane mode off

        Returns:
            True if successful
        """
        response = self.send_at(f"AT+CFUN={fun}", timeout=10000)
        if "OK" in response:
            time.sleep(2)
            return True
        return False

    def get_network_registration(self) -> tuple[int, int]:
        """Get network registration status (CREG and CGREG).

        Returns:
            Tuple of (n, stat) where n is network status
            stat: 0=not registered, 1=registered, 2=searching, 3=denied
        """
        response = self.send_at("AT+CREG?")
        stat = 0

        if "+CREG:" in response:
            try:
                # Format: +CREG: <n>,<stat>
                # Example: +CREG: 0,1
                start = response.find("+CREG:")
                if start != -1:
                    comma_pos = response.find(",", start)
                    if comma_pos != -1:
                        stat_str = response[comma_pos + 1 : comma_pos + 3].strip()
                        stat = int(stat_str)
            except (ValueError, IndexError):
                pass

        return (0, stat)

    def get_gprs_registration(self) -> int:
        """Get GPRS network registration status.

        Returns:
            Registration stat: 0=not registered, 1=registered
        """
        response = self.send_at("AT+CGREG?")
        if "+CGREG:" in response:
            try:
                start = response.find("+CGREG:")
                if start != -1:
                    comma_pos = response.find(",", start)
                    if comma_pos != -1:
                        stat_str = response[comma_pos + 1 : comma_pos + 3].strip()
                        return int(stat_str)
            except (ValueError, IndexError):
                pass
        return 0

    def check_sim_status(self) -> str:
        """Check SIM card status."""
        return self.send_at("AT+CPIN?", timeout=3000)

    def check_network_registration(self) -> str:
        """Check network registration status."""
        return self.send_at("AT+CREG?", timeout=3000)

    def check_gprs_registration(self) -> str:
        """Check GPRS registration status."""
        return self.send_at("AT+CGREG?", timeout=3000)

    def check_signal_quality(self) -> str:
        """Check signal quality."""
        return self.send_at("AT+CSQ", timeout=3000)

    def check_operator(self) -> str:
        """Check current operator."""
        return self.send_at("AT+COPS?", timeout=5000)

    def check_network_info(self) -> str:
        """Get full network information."""
        return self.send_at("AT+CPSI?", timeout=5000)

    def wait_for_network(self, timeout_ms: int = 60000) -> bool:
        """Wait for network registration.

        Args:
            timeout_ms: Maximum wait time in ms

        Returns:
            True if registered
        """
        start = time.ticks_ms()
        check_interval = 10000  # Check every 10 seconds
        last_check = 0

        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            _, stat = self.get_network_registration()
            gprs_stat = self.get_gprs_registration()

            if stat == 1 and gprs_stat == 1:
                self._log("Network registered")
                return True

            elapsed = time.ticks_diff(time.ticks_ms(), start)
            if elapsed - last_check > check_interval:
                self._log(f"Network check: CREG={stat}, CGREG={gprs_stat}")
                last_check = elapsed

            time.sleep(2)

        self._log("Network registration timeout")
        self._log("Diagnostics:")
        self._log(f"  SIM: {self.check_sim_status()}")
        self._log(f"  Network: {self.check_network_registration()}")
        self._log(f"  GPRS: {self.check_gprs_registration()}")
        self._log(f"  Signal: {self.check_signal_quality()}")
        self._log(f"  Operator: {self.check_operator()}")
        return False

    def set_apn(self, apn: str) -> bool:
        """Define PDP context.

        Args:
            apn: Access Point Name

        Returns:
            True if successful
        """
        response = self.send_at(f'AT+CGDCONT=1,"IP","{apn}"', timeout=5000)
        return "OK" in response

    def clear_pdp_contexts(self) -> None:
        """Delete unnecessary PDP contexts (especially IMS context).

        Some carriers (O2, Telekom) automatically create IMS context (cid=2)
        for VoLTE which can interfere with data connection.
        Must restart modem after clearing contexts.
        """
        self._log("Clearing unnecessary PDP contexts...")

        # Delete contexts 2-5 (IMS and other auto-created contexts)
        for cid in range(2, 6):
            response = self.send_at(f"AT+CGDCONT={cid}", timeout=3000)
            if "OK" in response:
                self._log(f"Deleted context {cid}")

        self._log("PDP contexts cleared (restart required)")

    def restart_modem(self) -> bool:
        """Restart modem (required after clearing PDP contexts).

        Returns:
            True if restart successful and modem is ready
        """
        self._log("Restarting modem...")
        response = self.send_at("AT+CFUN=1,1", timeout=10000)

        if "OK" not in response:
            self._log("Modem restart command failed")
            return False

        self._log("Modem restarting, waiting 20s...")

        # Wait for modem to fully restart
        time.sleep(15)

        # Wait for modem to respond to AT commands
        for attempt in range(10):
            try:
                resp = self.send_at("AT", timeout=3000)
                if "OK" in resp:
                    self._log(f"Modem ready after {(attempt + 1) * 3}s")
                    time.sleep(2)  # Extra stabilization time
                    return True
            except Exception:
                pass
            time.sleep(3)

        self._log("Modem did not respond after restart")
        return False

    def activate_pdp(self) -> bool:
        """Activate PDP context.

        Returns:
            True if successful
        """
        response = self.send_at("AT+CGACT=1,1", timeout=10000)
        return "OK" in response

    def open_network(self) -> bool:
        """Open network/socket service (required for TCP/IP).

        Returns:
            True if successful
        """
        self._log("Opening network service...")
        response = self.send_at("AT+NETOPEN", timeout=15000)
        if "OK" in response or "+NETOPEN:" in response:
            self._log("Network service opened")
            return True
        self._log(f"Network open failed: {response[:30]}")
        return False

    def close_network(self) -> bool:
        """Close network/socket service.

        Returns:
            True if successful
        """
        response = self.send_at("AT+NETCLOSE", timeout=10000)
        return "OK" in response

    def deactivate_pdp(self) -> bool:
        """Deactivate PDP context.

        Returns:
            True if successful
        """
        response = self.send_at("AT+CGACT=0,1", timeout=10000)
        return "OK" in response

    def connect_lte(
        self, apn: str, pin: str | None = None, timeout_ms: int = 60000
    ) -> bool:
        """Connect to LTE network.

        Args:
            apn: Access Point Name
            pin: SIM PIN (optional)
            timeout_ms: Connection timeout

        Returns:
            True if connected
        """
        self._log("Starting LTE connection...")

        if pin:
            self._log(f"Setting PIN: {pin}")
            self.set_pin(pin)

        self._log("Enabling phone function...")
        if not self.set_phone_function(1):
            self._log("Failed to enable phone function")
            return False

        self._log("Waiting for network...")
        if not self.wait_for_network(timeout_ms):
            self._log("Network registration failed")
            return False

        # Clear unnecessary PDP contexts and restart modem
        # Fixes issue where IMS context (cid=2) interferes with data connection
        self.clear_pdp_contexts()

        if not self.restart_modem():
            self._log("Modem restart failed")
            return False

        # Re-enable phone function after restart
        self._log("Re-enabling phone function after restart...")
        if not self.set_phone_function(1):
            self._log("Failed to re-enable phone function")
            return False

        # Wait for network registration after restart
        self._log("Waiting for network after restart...")
        if not self.wait_for_network(timeout_ms):
            self._log("Network registration failed after restart")
            return False

        self._log(f"Setting APN: {apn}")
        if not self.set_apn(apn):
            self._log("Failed to set APN")
            return False

        self._log("Activating PDP...")
        if not self.activate_pdp():
            self._log("Failed to activate PDP")
            return False

        # Open network service (required for TCP/IP operations)
        time.sleep(2)
        if not self.open_network():
            self._log("Failed to open network service")
            return False

        # Wait for IP address to be assigned (can take a few seconds)
        self._log("Waiting for IP address...")
        ip_addr = None
        for attempt in range(5):
            time.sleep(2)
            ip_addr = self.get_ip_address()
            if ip_addr:
                self._log(f"LTE IP: {ip_addr} (after {attempt + 1} attempts)")
                break
            self._log(f"IP attempt {attempt + 1}/5 failed, retrying...")

        if not ip_addr:
            self._log("No IP address received after 5 attempts")

        self.lte_connected = True
        self._log("LTE connected successfully")

        return True

    def get_ip_address(self) -> str | None:
        """Get the LTE IP address.

        Tries multiple AT commands to get the IP address.
        Returns:
            IP address string or None
        """
        # Method 1: AT+IPADDR (SIM7600 specific, requires AT+NETOPEN first)
        try:
            response = self.send_at("AT+IPADDR", timeout=3000)
            # Response: +IPADDR: 10.71.155.118
            if "+IPADDR:" in response:
                for line in response.split("\n"):
                    if "+IPADDR:" in line:
                        parts = line.split(":")
                        if len(parts) >= 2:
                            ip = parts[1].strip()
                            if ip and "." in ip and ip != "0.0.0.0":
                                return ip
        except Exception:
            pass

        # Method 2: AT+CGPADDR (standard, most reliable)
        try:
            response = self.send_at("AT+CGPADDR=1", timeout=3000)
            # Response: +CGPADDR: 1,10.126.84.47 (NO quotes!)
            if "+CGPADDR:" in response:
                # Find the line with the response
                for line in response.split("\n"):
                    if "+CGPADDR:" in line:
                        parts = line.split(",")
                        if len(parts) >= 2:
                            ip = parts[1].strip()
                            if ip and "." in ip and ip != "0.0.0.0":
                                return ip
        except Exception:
            pass

        # Method 2: AT+CGCONTRDP (detailed PDP context)
        try:
            response = self.send_at("AT+CGCONTRDP=1", timeout=3000)
            # Response: +CGCONTRDP: 1,5,"internet",...,10.1.1.1,...
            if "+CGCONTRDP:" in response:
                for line in response.split("\n"):
                    if "+CGCONTRDP:" in line:
                        # Find all comma-separated values
                        parts = line.split(",")
                        for part in parts:
                            part = part.strip().strip('"')
                            if part and "." in part and any(c.isdigit() for c in part):
                                # Check if it looks like an IP
                                ip_parts = part.split(".")
                                if len(ip_parts) == 4 and all(
                                    p.isdigit() for p in ip_parts
                                ):
                                    if part != "0.0.0.0":
                                        return part
        except Exception:
            pass

        return None

    def disconnect_lte(self) -> bool:
        """Disconnect from LTE network."""
        self.deactivate_pdp()
        self.set_phone_function(0)
        self.lte_connected = False
        self._log("LTE disconnected")
        return True

    def is_connected(self) -> bool:
        """Check if LTE is connected.

        Returns:
            True if connected
        """
        if not self.lte_connected:
            return False

        _, stat = self.get_network_registration()
        gprs_stat = self.get_gprs_registration()

        return stat == 1 and gprs_stat == 1

    # -------------------------------------------------------------------------
    # Signal Quality
    # -------------------------------------------------------------------------
    def get_signal_quality(self) -> tuple[int, int]:
        """Get signal quality (RSSI and BER).

        Returns:
            Tuple of (rssi, ber)
            rssi: 0-31 (99 = not detectable)
            ber: 0-7 (99 = not detectable)
        """
        response = self.send_at("AT+CSQ")

        if "+CSQ:" in response:
            try:
                start = response.find("+CSQ:") + 6
                data = response[start:].strip()
                parts = data.split(",")
                rssi = int(parts[0].strip())
                # Handle "99\n\nOK" case - extract just the number
                ber_str = parts[1].strip().split("\n")[0].strip()
                ber = int(ber_str) if ber_str.isdigit() else 99
                return (rssi, ber)
            except (ValueError, IndexError):
                pass

        return (99, 99)

    def get_rssi_dbm(self) -> int:
        """Get RSSI in dBm.

        Returns:
            RSSI in dBm (-113 to -51 dBm), or -999 if not detectable
        """
        rssi, _ = self.get_signal_quality()
        if rssi == 99:
            return -999  # Sentinel value for "not detectable"
        return -113 + (rssi * 2)

    def get_signal_quality_text(self) -> str:
        """Get signal quality as text.

        Returns:
            Quality string: excellent, good, fair, poor, no signal
        """
        rssi, _ = self.get_signal_quality()

        if rssi >= 20:
            return "excellent"
        elif rssi >= 15:
            return "good"
        elif rssi >= 10:
            return "fair"
        elif rssi >= 5:
            return "poor"
        else:
            return "no signal"

    # -------------------------------------------------------------------------
    # Network Information
    # -------------------------------------------------------------------------
    def get_operator(self) -> str:
        """Get current network operator.

        Returns:
            Operator name or empty string
        """
        response = self.send_at("AT+COPS?", timeout=10000)

        if "+COPS:" in response:
            try:
                start = response.find('"') + 1
                end = response.find('"', start)
                if start > 0 and end > start:
                    return response[start:end]
            except (ValueError, IndexError):
                pass

        return ""

    def get_network_type(self) -> str:
        """Get network type (LTE, WCDMA, etc).

        Returns:
            Network type string
        """
        response = self.send_at("AT+CPSI?")

        if "+CPSI:" in response:
            try:
                parts = response.split(",")
                if len(parts) >= 2:
                    system = parts[1].strip().strip('"')
                    if "LTE" in system:
                        return "LTE"
                    elif "WCDMA" in system:
                        return "WCDMA"
                    elif "TD-SCDMA" in system:
                        return "TD-SCDMA"
                    elif "GSM" in system:
                        return "GSM"
                    return system
            except (ValueError, IndexError):
                pass

        return "UNKNOWN"

    # -------------------------------------------------------------------------
    # GPS Functions
    # -------------------------------------------------------------------------
    def enable_gps(self) -> bool:
        """Enable GPS with antenna power (CGNS stack).

        Checks GPS status first, then enables only if needed.
        GPS data retrieval (AT+CGPSINFO) works even if this returns False,
        so we check and mark gps_enabled based on GPS functionality.

        Returns:
            True if GPS is working (enabled or successfully enabled)
        """
        if self.gps_enabled:
            self._log("GPS already enabled")
            return True

        # First, try to enable GPS antenna power
        self.send_at("AT+CVAUXS=1", timeout=3000)
        self.send_at("AT+CVAUXV=3300", timeout=3000)
        time.sleep(1)

        # Try enabling CGNS (combined GNSS) power
        response = self.send_at("AT+CGNSPWR=1", timeout=3000)
        if "OK" in response:
            self.gps_enabled = True
            self.gps_configured = True
            self._log("GPS CGNS enabled")
            return True

        # GPS might already be enabled - check by trying to get data
        # If AT+CGPSINFO returns valid data, GPS is working
        test_response = self.send_at("AT+CGPSINFO", timeout=3000)
        if "+CGPSINFO:" in test_response and len(test_response) > 20:
            # GPS is already working, just mark as enabled
            self.gps_enabled = True
            self.gps_configured = True
            self._log("GPS already active (CGPSINFO working)")
            return True

        self._log("GPS enable failed")
        return False

    def get_gps_fix_status(self) -> tuple[int, int]:
        """Get GPS fix status.

        Tries AT+CGNSFPS first, falls back to checking AT+CGNSINFO response.

        Returns:
            Tuple of (fix_status, satellites)
            - fix_status: 0=no fix, 1=fix acquired
            - satellites: Number of satellites used
        """
        # Try CGNSFPS first
        response = self.send_at("AT+CGNSFPS?", timeout=3000)

        if "+CGNSFPS:" in response:
            try:
                start = response.find("+CGNSFPS:") + 10
                data = response[start:].strip()
                parts = data.split(",")
                fix = int(parts[0].strip())
                sats = int(parts[1].strip()) if len(parts) > 1 else 0
                return (fix, sats)
            except (ValueError, IndexError):
                pass

        # Fallback: check CGNSINFO response for fix status
        response = self.send_at("AT+CGNSINFO", timeout=3000)
        if "+CGNSINF:" in response:
            try:
                data_start = response.rfind(":") + 1
                data = response[data_start:].strip()
                parts = data.split(",")

                if len(parts) > 2:
                    run = parts[0].strip()
                    fix = parts[1].strip()
                    if run == "1" and fix == "1":
                        # Count satellites from visible field if available
                        sats = 0
                        if len(parts) > 13 and parts[13].strip():
                            try:
                                sats = int(parts[13].strip())
                            except ValueError:
                                pass
                        return (1, sats)
            except (ValueError, IndexError):
                pass

        return (0, 0)

    def get_gps_location_cgnsinfo(self) -> dict | None:
        """Get GPS data using AT+CGNSINFO (primary, rich data).

        AT+CGNSINFO returns:
        <run>,<fix>,<utc>,<lat>,<lat_dir>,<lon>,<lon_dir>,
        <alt>,<spd>,<course>,<pdop>,<hdop>,<vdop>,<sats>,...

        Returns:
            Dict with full GPS data or None.
        """
        response = self.send_at("AT+CGNSINFO", timeout=3000)

        if "+CGNSINF:" not in response:
            return None

        try:
            data_start = response.rfind(":") + 1
            data = response[data_start:].strip()

            if not data or data == "":
                return None

            parts = data.split(",")

            # Debug: log raw response
            self._log(f"CGNSINFO raw: {data[:100]}")

            # Check run and fix status
            run_status = parts[0].strip() if len(parts) > 0 else ""
            fix_status = parts[1].strip() if len(parts) > 1 else ""

            if run_status != "1" or fix_status != "1":
                return None

            # Parse latitude
            lat_raw = parts[3].strip() if len(parts) > 3 else ""
            lat_dir = parts[4].strip() if len(parts) > 4 else ""

            if not lat_raw or not lat_dir:
                return None

            lat = self._convert_nmea_lat(lat_raw, lat_dir)

            # Parse longitude
            lon_raw = parts[5].strip() if len(parts) > 5 else ""
            lon_dir = parts[6].strip() if len(parts) > 6 else ""

            if not lon_raw or not lon_dir:
                return None

            lon = self._convert_nmea_lon(lon_raw, lon_dir)

            # Validate coordinates
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return None

            # Parse altitude (meters)
            alt = 0.0
            if len(parts) > 7 and parts[7].strip():
                try:
                    alt = float(parts[7].strip())
                except ValueError:
                    pass

            # Parse speed and course
            # CGNSINFO format: <alt>,<speed>,<course>,<pdop>,...
            speed = 0.0
            course = 0.0
            if len(parts) > 9:
                try:
                    speed = float(parts[8].strip()) if parts[8].strip() else 0.0
                    course = float(parts[9].strip()) if parts[9].strip() else 0.0
                except (ValueError, IndexError):
                    pass

            # Parse PDOP
            pdop = 0.0
            if len(parts) > 10 and parts[10].strip():
                try:
                    pdop = float(parts[10].strip())
                except ValueError:
                    pass

            # Parse HDOP
            hdop = 0.0
            if len(parts) > 11 and parts[11].strip():
                try:
                    hdop = float(parts[11].strip())
                except ValueError:
                    pass

            # Parse VDOP
            vdop = 0.0
            if len(parts) > 12 and parts[12].strip():
                try:
                    vdop = float(parts[12].strip())
                except ValueError:
                    pass

            # Parse visible satellites
            sats_visible = 0
            if len(parts) > 13 and parts[13].strip():
                try:
                    sats_visible = int(parts[13].strip())
                except ValueError:
                    pass

            # Parse GPS/GLONASS/BeiDou satellites (used)
            gps_svs = 0
            if len(parts) > 14 and parts[14].strip():
                try:
                    gps_svs = int(parts[14].strip())
                except ValueError:
                    pass

            glonass_svs = 0
            if len(parts) > 15 and parts[15].strip():
                try:
                    glonass_svs = int(parts[15].strip())
                except ValueError:
                    pass

            beidou_svs = 0
            if len(parts) > 16 and parts[16].strip():
                try:
                    beidou_svs = int(parts[16].strip())
                except ValueError:
                    pass

            self._log(f"GPS: lat={lat}, lon={lon}, speed={speed}, course={course}")

            return {
                "latitude": lat,
                "longitude": lon,
                "altitude": round(alt, 1),
                "speed": round(speed, 1),
                "course": round(course, 1),
                "pdop": round(pdop, 1),
                "hdop": round(hdop, 1),
                "vdop": round(vdop, 1),
                "satellites": sats_visible,
                "satellites_gps": gps_svs,
                "satellites_glonass": glonass_svs,
                "satellites_beidou": beidou_svs,
                "source": "CGNSINFO",
            }

        except Exception as e:
            self._log(f"CGNSINFO parse error: {e}")
            return None

    def get_gps_location_cgpsinfo(self) -> dict | None:
        """Get GPS data using AT+CGPSINFO (fallback, simpler data).

        AT+CGPSINFO returns:
        <lat>,<N/S>,<lon>,<E/W>,<date>,<UTC time>,<alt>,<speed>,<course>

        Note: speed is in knots, we convert to km/h.

        Returns:
            Dict with GPS data or None.
        """
        response = self.send_at("AT+CGPSINFO", timeout=3000)

        if "+CGPSINFO:" not in response:
            return None

        try:
            data_start = response.rfind(":") + 1
            data = response[data_start:].strip()

            if not data or "," not in data:
                return None

            parts = data.split(",")

            # Check for valid data (empty means no fix)
            if len(parts) < 6 or not parts[0].strip():
                return None

            # Parse latitude: parts[0] = lat, parts[1] = N/S
            lat_raw = parts[0].strip()
            lat_dir = parts[1].strip()
            lat = self._convert_nmea_lat(lat_raw, lat_dir)

            # Parse longitude: parts[2] = lon, parts[3] = E/W
            lon_raw = parts[2].strip()
            lon_dir = parts[3].strip()
            lon = self._convert_nmea_lon(lon_raw, lon_dir)

            # Validate coordinates
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return None

            # Parse altitude (meters): parts[6]
            alt = 0.0
            if len(parts) > 6 and parts[6].strip():
                try:
                    alt = float(parts[6].strip())
                except ValueError:
                    pass

            # Parse speed (knots, convert to km/h): parts[7]
            # 1 knot = 1.852 km/h
            speed_knots = 0.0
            if len(parts) > 7 and parts[7].strip():
                try:
                    speed_knots = float(parts[7].strip())
                except ValueError:
                    pass
            speed_kmh = speed_knots * 1.852

            # Parse course (degrees): parts[8]
            course = 0.0
            if len(parts) > 8 and parts[8].strip():
                try:
                    course = float(parts[8].strip())
                except ValueError:
                    pass

            return {
                "latitude": lat,
                "latitude_dir": lat_dir,
                "longitude": lon,
                "longitude_dir": lon_dir,
                "altitude": round(alt, 1),
                "speed": round(speed_kmh, 1),
                "course": round(course, 1),
                # Accuracy fields left as None - will be filled by CGNSINFO if available
                "source": "CGPSINFO",
            }

        except Exception as e:
            self._log(f"CGPSINFO parse error: {e}")
            return None

        try:
            data_start = response.rfind(":") + 1
            data = response[data_start:].strip()

            if not data or "," not in data:
                return None

            parts = data.split(",")

            # Check for valid data (empty means no fix)
            if len(parts) < 4 or not parts[0].strip():
                return None

            # Parse latitude
            lat_raw = parts[0].strip()
            lat_dir = parts[1].strip()
            lat = self._convert_nmea_lat(lat_raw, lat_dir)

            # Parse longitude
            lon_raw = parts[2].strip()
            lon_dir = parts[3].strip()
            lon = self._convert_nmea_lon(lon_raw, lon_dir)

            # Validate coordinates
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return None

            # Parse altitude (not provided by CGPSINFO)
            alt = 0.0

            # Parse speed (km/h)
            speed = 0.0
            if len(parts) > 6 and parts[6].strip():
                try:
                    speed = float(parts[6].strip())
                except ValueError:
                    pass

            # Parse course (degrees)
            course = 0.0
            if len(parts) > 7 and parts[7].strip():
                try:
                    course = float(parts[7].strip())
                except ValueError:
                    pass

            return {
                "latitude": lat,
                "longitude": lon,
                "altitude": alt,
                "speed": round(speed, 1),
                "course": round(course, 1),
                "pdop": 0.0,
                "hdop": 0.0,
                "vdop": 0.0,
                "satellites": 0,
                "satellites_gps": 0,
                "satellites_glonass": 0,
                "satellites_beidou": 0,
                "source": "CGPSINFO",
            }

        except Exception as e:
            self._log(f"CGPSINFO parse error: {e}")
            return None

    def get_gnss_info(self) -> dict | None:
        """Get GPS data - CGPSINFO for basic data, CGNSINFO for accuracy data.

        Strategy:
        - CGPSINFO: Primary source for lat, lon, date, time, alt, speed, course
        - CGNSINFO: Supplement with PDOP, HDOP, VDOP, satellites (if available)

        Returns:
            Dict with full GPS data or None.
        """
        # First, get basic data from CGPSINFO
        basic = self.get_gps_location_cgpsinfo()
        if not basic:
            return None

        # Try to get extra accuracy data from CGNSINFO
        extra = self.get_gps_accuracy_from_cgnsinfo()
        if extra:
            # Merge extra data into basic
            basic.update(extra)

        return basic

    def get_gps_accuracy_from_cgnsinfo(self) -> dict | None:
        """Get accuracy data from AT+CGNSINFO.

        CGNSINFO provides: PDOP, HDOP, VDOP, satellites, GNSS satellite counts

        Returns:
            Dict with accuracy data or empty dict if not available.
        """
        response = self.send_at("AT+CGNSINFO", timeout=3000)

        if "+CGNSINF:" not in response:
            return None

        try:
            data_start = response.rfind(":") + 1
            data = response[data_start:].strip()

            if not data or data == "":
                return None

            parts = data.split(",")

            # Check run and fix status
            run_status = parts[0].strip() if len(parts) > 0 else ""
            fix_status = parts[1].strip() if len(parts) > 1 else ""

            if run_status != "1" or fix_status != "1":
                return None

            result = {}

            # Parse PDOP (index 10)
            if len(parts) > 10 and parts[10].strip():
                try:
                    result["pdop"] = round(float(parts[10].strip()), 1)
                except ValueError:
                    pass

            # Parse HDOP (index 11)
            if len(parts) > 11 and parts[11].strip():
                try:
                    result["hdop"] = round(float(parts[11].strip()), 1)
                except ValueError:
                    pass

            # Parse VDOP (index 12)
            if len(parts) > 12 and parts[12].strip():
                try:
                    result["vdop"] = round(float(parts[12].strip()), 1)
                except ValueError:
                    pass

            # Parse visible satellites (index 13)
            if len(parts) > 13 and parts[13].strip():
                try:
                    result["satellites"] = int(parts[13].strip())
                except ValueError:
                    pass

            # Parse GPS satellites (index 14)
            if len(parts) > 14 and parts[14].strip():
                try:
                    result["satellites_gps"] = int(parts[14].strip())
                except ValueError:
                    pass

            # Parse GLONASS satellites (index 15)
            if len(parts) > 15 and parts[15].strip():
                try:
                    result["satellites_glonass"] = int(parts[15].strip())
                except ValueError:
                    pass

            # Parse BeiDou satellites (index 16)
            if len(parts) > 16 and parts[16].strip():
                try:
                    result["satellites_beidou"] = int(parts[16].strip())
                except ValueError:
                    pass

            return result

        except Exception as e:
            self._log(f"CGNSINFO accuracy parse error: {e}")
            return None

    def get_gps_location(self, timeout_ms: int = 5000) -> dict | None:
        """Get GPS location using AT+CGNSINFO (CGNS stack).

        Args:
            timeout_ms: Maximum wait time for fix

        Returns:
            Dict with lat, lon, alt, speed, satellites, pdop or None
        """
        if not self.gps_enabled:
            self.enable_gps()

        start = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            result = self.get_gnss_info()

            if result:
                lat = result.get("latitude", 0)
                lon = result.get("longitude", 0)

                if lat != 0 and lon != 0:
                    return result

            time.sleep(0.5)

        return None

    def _convert_nmea_lat(self, raw: str, direction: str) -> float:
        """Convert NMEA latitude to decimal degrees.

        Args:
            raw: NMEA format latitude (DDMM.MMMM)
            direction: N or S

        Returns:
            Latitude in decimal degrees
        """
        try:
            if len(raw) < 4:
                return 0.0

            degrees = float(raw[:2])
            minutes = float(raw[2:])
            lat = degrees + minutes / 60.0

            if direction == "S":
                lat = -lat

            return round(lat, 6)
        except (ValueError, IndexError, TypeError):
            return 0.0

    def _convert_nmea_lon(self, raw: str, direction: str) -> float:
        """Convert NMEA longitude to decimal degrees.

        Args:
            raw: NMEA format longitude (DDDMM.MMMM)
            direction: E or W

        Returns:
            Longitude in decimal degrees
        """
        try:
            if len(raw) < 5:
                return 0.0

            degrees = float(raw[:3])
            minutes = float(raw[3:])
            lon = degrees + minutes / 60.0

            if direction == "W":
                lon = -lon

            return round(lon, 6)
        except (ValueError, IndexError, TypeError):
            return 0.0

    # -------------------------------------------------------------------------
    # Time Functions
    # -------------------------------------------------------------------------
    def get_network_time(self) -> str | None:
        """Get time from network registration (AT+CCLK).

        Note: This returns the operator's network time string.
        For system time sync, use sync_time() from lte_utils.py.

        Returns:
            Time string or None
        """
        response = self.send_at("AT+CCLK?", timeout=3000)
        if "+CCLK:" in response:
            try:
                start = response.find("+CCLK:") + 8
                end = response.find('"', start)
                if end > start:
                    return response[start:end]
            except Exception:
                pass
        return None

    def get_gps_time(self) -> tuple[int, int, int, int, int, int] | None:
        """Get time from GPS data (AT+CGPSINFO).

        Parses UTC time and date from GPS response.
        Format: AT+CGPSINFO returns <lat>,<N/S>,<lon>,<E/W>,<date>,<UTC time>,...

        Returns:
            Tuple (year, month, day, hour, minute, second) or None
        """
        response = self.send_at("AT+CGPSINFO", timeout=3000)
        if "+CGPSINFO:" not in response:
            return None

        try:
            data_start = response.rfind(":") + 1
            data = response[data_start:].strip()
            parts = data.split(",")

            if len(parts) < 6:
                return None

            lat = parts[0].strip()
            if not lat:
                return None

            date_str = parts[4].strip()
            utc_time = parts[5].strip()

            if not date_str or not utc_time or date_str == "":
                return None

            hour = int(utc_time[0:2])
            minute = int(utc_time[2:4])
            second = int(utc_time[4:6])

            day = int(date_str[0:2])
            month = int(date_str[2:4])
            year = int(date_str[4:6]) + 2000

            return (year, month, day, hour, minute, second)
        except Exception:
            return None


class SIM7600Manager:
    """Manager for SIM7600 with retry logic."""

    def __init__(
        self,
        sim: SIM7600,
        apn: str,
        pin: str | None = None,
        retry_interval_ms: int = 60000,
    ) -> None:
        """Initialize SIM7600 manager.

        Args:
            sim: SIM7600 instance
            apn: Access Point Name
            pin: SIM PIN (optional)
            retry_interval_ms: Retry interval for failed connection
        """
        self.sim = sim
        self.apn = apn
        self.pin = pin
        self.retry_interval_ms = retry_interval_ms

        self._initialized = False
        self._last_init = 0

    def set_logger(self, logger) -> None:
        """Set logging function."""
        self.sim.set_logger(logger)

    def init(self) -> bool:
        """Initialize SIM7600.

        Returns:
            True if initialized
        """
        now = time.ticks_ms()

        if self._initialized:
            return True

        if time.ticks_diff(now, self._last_init) < self.retry_interval_ms:
            return False

        self._last_init = now

        if self.sim.init():
            self._initialized = True
            return True

        return False

    def connect(self) -> bool:
        """Connect to LTE network.

        Returns:
            True if connected
        """
        if not self.init():
            return False

        return self.sim.connect_lte(self.apn, self.pin)

    def is_connected(self) -> bool:
        """Check if LTE is connected.

        Returns:
            True if connected
        """
        return self.sim.is_connected()

    def get_ip_address(self) -> str | None:
        """Get the LTE IP address.

        Returns:
            IP address string or None
        """
        return self.sim.get_ip_address()

    def get_signal_info(self) -> dict:
        """Get signal information.

        Returns:
            Dict with rssi, quality
        """
        rssi = self.sim.get_rssi_dbm()
        quality = self.sim.get_signal_quality_text()

        return {
            "rssi": rssi,
            "quality": quality,
        }

    def get_network_info(self) -> dict:
        """Get network information.

        Returns:
            Dict with operator, type, registered
        """
        return {
            "operator": self.sim.get_operator(),
            "type": self.sim.get_network_type(),
            "registered": self.sim.is_connected(),
        }

    def get_gps_location(self, timeout_ms: int = 5000) -> dict | None:
        """Get GPS location with all data.

        Args:
            timeout_ms: Maximum wait time for GPS fix

        Returns:
            Dict with GPS data or None
        """
        return self.sim.get_gps_location(timeout_ms=timeout_ms)

    def get_gps_fix_status(self) -> tuple[int, int]:
        """Get GPS fix status.

        Returns:
            Tuple of (fix_status, satellites)
            - fix_status: 0=no fix, 1=fix acquired
            - satellites: Number of satellites used
        """
        return self.sim.get_gps_fix_status()
