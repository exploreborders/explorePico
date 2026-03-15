"""
SIM7600G-H 4G LTE Driver for Pico 2W

Hardware:
    - Module: SIM7600G-H (SIMCom)
    - Interface: UART
    - Features: 4G LTE, GPS, MQTT, TCP/IP

Features:
    - LTE network connection (4G/3G/2G)
    - GPS positioning (GPS/GLONASS/BeiDou/Galileo)
    - Time sync from GPS
    - Signal quality monitoring
    - Network information

AT Commands:
    - Basic: AT, ATI
    - Network: AT+CFUN, AT+CREG, AT+CGREG, AT+COPS
    - GPRS: AT+CGDCONT, AT+CGACT
    - GPS: AT+CGPS, AT+CGPSINFO
    - Signal: AT+CSQ
    - MQTT: AT+CMQTTSTART, etc.
    - Time: AT+CCLK

Usage:
    from sensors.sim7600 import SIM7600

    sim = SIM7600(uart_id=0, tx_pin=1, rx_pin=0)
    sim.init()
    sim.connect_lte(apn="internet", pin="5046")
    location = sim.get_gps_location()
"""

import time
import machine
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
                    data = self.uart.read(64)
                    if data:
                        response += data.decode("utf-8", "ignore")

                if "OK" in response or "ERROR" in response:
                    break

            return response.strip()

        except Exception as e:
            return ""

    def _try_baud(self, baud: int) -> bool:
        """Try a specific baud rate with better response handling."""
        try:
            if self.uart:
                self.uart.deinit()
                time.sleep(0.3)

            self.uart = UART(
                self.uart_id,
                baud,
                tx=Pin(self.tx_pin),
                rx=Pin(self.rx_pin),
            )
            self.uart.init(baud, bits=8, parity=None, stop=1)
            time.sleep(1)

            self._log(f"Testing {baud} baud...")

            for attempt in range(5):
                # Clear any stale data
                while self.uart.any():
                    self.uart.read(100)
                time.sleep(0.5)

                # Send AT command
                self.uart.write(b"AT\r\n")

                # Wait and collect response
                response = ""
                for _ in range(20):  # More iterations
                    if self.uart.any():
                        data = self.uart.read(128)  # Larger buffer
                        if data:
                            decoded = data.decode("utf-8", "ignore")
                            response += decoded

                    if "OK" in response:
                        self.baudrate = baud
                        self._log(f"SUCCESS at {baud} baud!")
                        return True

                    if "ERROR" in response:
                        break

                    time.sleep(0.5)  # Wait longer between reads

                # Log what we got
                if response:
                    self._log(f"Final response at {baud}: {response[:80]}")
                else:
                    self._log(f"No response at {baud}")

            return False

        except Exception as e:
            self._log(f"Baud {baud} error: {e}")
            return False

    def init(self) -> bool:
        """Initialize UART communication with SIM7600.

        Returns:
            True if SIM7600 responds to AT command
        """
        # If baud rate was manually set, try only that one
        if self.baudrate and self.baudrate > 0:
            baud_rates = [self.baudrate]
            self._log(f"Using manually set baud rate: {self.baudrate}")
        else:
            baud_rates = [115200, 57600, 38400, 19200, 9600, 230400, 460800, 4800, 2400]
            self._log("Starting auto-baud detection...")

        self._log("Waiting 15s for module to fully boot...")
        time.sleep(15)

        for baud in baud_rates:
            self._log(f"Trying baud rate: {baud}")
            if self._try_baud(baud):
                self._log(f"Connected at {baud} baud!")

                self._log("Getting module info...")
                for _ in range(2):
                    resp = self._send_at_simple("ATI", timeout=3000)
                    if resp:
                        self._log(f"Module: {resp[:100]}")
                        break

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

        self._log("No working baud rate found")
        return False

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

    def send_at_raw(self, command: str, timeout: int = 1000) -> str:
        """Send AT command and return raw response.

        Args:
            command: AT command
            timeout: Timeout in ms

        Returns:
            Raw response string
        """
        if not self.uart:
            return ""

        try:
            self.uart.write(command.encode() + b"\r\n")
            start = time.ticks_ms()
            response = ""

            while time.ticks_diff(time.ticks_ms(), start) < timeout:
                if self.uart.any():
                    char = self.uart.read(1)
                    if char:
                        response += char.decode("utf-8", "ignore")
                else:
                    time.sleep(0.01)

            return response.strip()

        except Exception:
            return ""

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
            except:
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
            except:
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

    def activate_pdp(self) -> bool:
        """Activate PDP context.

        Returns:
            True if successful
        """
        response = self.send_at("AT+CGACT=1,1", timeout=10000)
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

        self._log(f"Setting APN: {apn}")
        if not self.set_apn(apn):
            self._log("Failed to set APN")
            return False

        self._log("Activating PDP...")
        if not self.activate_pdp():
            self._log("Failed to activate PDP")
            return False

        self.lte_connected = True
        self._log("LTE connected successfully")
        return True

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
                end = response.find(",", start)
                parts = response[start:end].split(",")
                rssi = int(parts[0].strip())
                ber = int(parts[1].strip())
                return (rssi, ber)
            except:
                pass

        return (99, 99)

    def get_rssi_dbm(self) -> int:
        """Get RSSI in dBm.

        Returns:
            RSSI in dBm (-113 to -51 dBm), or 0 if not detectable
        """
        rssi, _ = self.get_signal_quality()
        if rssi == 99:
            return 0
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
            except:
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
            except:
                pass

        return "UNKNOWN"

    # -------------------------------------------------------------------------
    # GPS Functions
    # -------------------------------------------------------------------------
    def enable_gps(self) -> bool:
        """Enable GPS.

        Returns:
            True if successful
        """
        response = self.send_at("AT+CGPS=1,1", timeout=5000)
        if "OK" in response:
            self.gps_enabled = True
            self._log("GPS enabled")
            return True
        return False

    def disable_gps(self) -> bool:
        """Disable GPS.

        Returns:
            True if successful
        """
        response = self.send_at("AT+CGPS=0", timeout=5000)
        if "OK" in response:
            self.gps_enabled = False
            self._log("GPS disabled")
            return True
        return False

    def get_gps_info(self) -> dict | None:
        """Get GPS information.

        Returns:
            Dict with lat, lon, alt, speed, satellites, or None if no fix
        """
        response = self.send_at("AT+CGPSINFO", timeout=3000)

        if "+CGPSINFO:" not in response or response == "ERROR":
            return None

        try:
            start = response.find("+CGPSINFO:") + 11
            data = response[start:].strip()

            if not data or data == ",":
                return None

            parts = data.split(",")

            if len(parts) < 6:
                return None

            lat_raw = parts[0].strip()
            lat_dir = parts[1].strip()
            lon_raw = parts[2].strip()
            lon_dir = parts[3].strip()
            date = parts[4].strip()
            time_raw = parts[5].strip()
            alt = (
                float(parts[6].strip()) if len(parts) > 6 and parts[6].strip() else 0.0
            )
            speed = (
                float(parts[7].strip()) if len(parts) > 7 and parts[7].strip() else 0.0
            )

            if not lat_raw or not lon_raw:
                return None

            lat = self._convert_nmea_lat(lat_raw, lat_dir)
            lon = self._convert_nmea_lon(lon_raw, lon_dir)

            return {
                "latitude": lat,
                "longitude": lon,
                "altitude": alt,
                "speed": speed,
                "date": date,
                "time": time_raw,
                "satellites": 0,
            }

        except Exception as e:
            self._log(f"GPS parse error: {e}")
            return None

    def get_gps_location(self, timeout_ms: int = 30000) -> dict | None:
        """Get GPS location, waiting for fix.

        Args:
            timeout_ms: Maximum wait time for fix

        Returns:
            Dict with lat, lon, alt, speed, satellites, or None
        """
        if not self.gps_enabled:
            self.enable_gps()

        start = time.ticks_ms()
        last_result = None

        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            result = self.get_gps_info()

            if result:
                lat = result.get("latitude", 0)
                lon = result.get("longitude", 0)

                if lat != 0 and lon != 0:
                    return result

            last_result = result
            time.sleep(2)

        return last_result

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
        except:
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
        except:
            return 0.0

    # -------------------------------------------------------------------------
    # Time Functions
    # -------------------------------------------------------------------------
    def get_network_time(self) -> str | None:
        """Get network time from SIM7600.

        Returns:
            ISO format time string or None
        """
        response = self.send_at("AT+CCLK?")

        if "+CCLK:" in response:
            try:
                start = response.find('"') + 1
                end = response.find('"', start)
                if start > 0 and end > start:
                    return response[start:end]
            except:
                pass

        return None

    def get_gps_time(self) -> str | None:
        """Get GPS time from NMEA.

        Returns:
            ISO format time string or None
        """
        gps = self.get_gps_info()

        if gps and gps.get("time") and gps.get("date"):
            try:
                time_str = gps["time"]
                date_str = gps["date"]

                hour = int(time_str[:2])
                minute = int(time_str[2:4])
                second = int(time_str[4:6])
                day = int(date_str[:2])
                month = int(date_str[2:4])
                year = int(date_str[4:6]) + 2000

                return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}"
            except:
                pass

        return None

    def sync_time_from_gps(self, timeout_ms: int = 60000) -> bool:
        """Sync Pico system time from GPS.

        Args:
            timeout_ms: Maximum wait time for GPS fix

        Returns:
            True if time was synced
        """
        self._log("Syncing time from GPS...")

        if not self.gps_enabled:
            self.enable_gps()

        gps_time = None
        start = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            gps = self.get_gps_info()

            if gps and gps.get("time") and gps.get("date"):
                try:
                    time_str = gps["time"]
                    date_str = gps["date"]

                    self._log(f"GPS date: {date_str}, time: {time_str}")

                    hour = int(time_str[:2])
                    minute = int(time_str[2:4])
                    second = int(time_str[4:6])
                    day = int(date_str[:2])
                    month = int(date_str[2:4])
                    year = int(date_str[4:6]) + 2000

                    rtc = machine.RTC()
                    rtc.datetime((year, month, day, 0, hour, minute, second, 0))

                    self._log(
                        f"GPS time synced: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
                    )
                    return True

                except Exception as e:
                    self._log(f"GPS time sync error: {e}")

            time.sleep(2)

        self._log(f"GPS time sync timeout after {timeout_ms}ms")
        self._log("GPS time sync failed, trying network time...")
        return self.sync_time_from_network()

    def sync_time_from_network(self) -> bool:
        """Sync Pico system time from network.

        Returns:
            True if time was synced
        """
        net_time = self.get_network_time()

        if net_time:
            self._log(f"Raw network time: {net_time}")
            try:
                date_time = net_time.split(",")[0]
                time_part = net_time.split(",")[1].split("+")[0].strip()

                date_parts = date_time.split("/")
                year = int(date_parts[0]) + 2000
                month = int(date_parts[1])
                day = int(date_parts[2])

                time_parts = time_part.split(":")
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                second = int(time_parts[2])

                rtc = machine.RTC()
                rtc.datetime((year, month, day, 0, hour, minute, second, 0))

                self._log(
                    f"Network time synced: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
                )
                return True

            except Exception as e:
                self._log(f"Network time sync error: {e}, raw: {net_time}")

        return False


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

    def get_gps_location(self) -> dict | None:
        """Get GPS location.

        Returns:
            Dict with GPS data or None
        """
        return self.sim.get_gps_location()

    def sync_time(self) -> bool:
        """Sync time from GPS.

        Returns:
            True if synced
        """
        return self.sim.sync_time_from_gps()
