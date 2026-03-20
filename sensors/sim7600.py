"""
SIM7600G-H 4G LTE Driver for Pico 2W

Hardware:
    - Module: SIM7600G-H (SIMCom)
    - Interface: UART
    - Features: 4G LTE, GPS, MQTT, TCP/IP

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
        """Enable GPS with antenna power (CGNS stack only).

        Enables CGNS engine for continuous positioning.
        Use sync_time_from_network() for time sync.

        Returns:
            True if successful
        """
        if self.gps_enabled:
            return True

        self.send_at("AT+CVAUXS=1", timeout=3000)
        self._log("GPS antenna power enabled")

        self.send_at("AT+CVAUXV=3300", timeout=3000)
        self._log("GPS antenna voltage set to 3.3V")

        time.sleep(1)

        self.send_at("AT+CGNSPWR=1", timeout=3000)
        self._log("GPS CGNS engine powered on")

        resp = self.send_at("AT+CGNSSMODE=1,1,1,1", timeout=3000)
        if "ERROR" in resp:
            self.send_at("AT+CGNSSMODE=1,1", timeout=3000)
            self._log("GPS GNSS mode: GPS+GLONASS")
        else:
            self._log("GPS GNSS mode: GPS+GLONASS+Galileo+BeiDou")

        time.sleep(1.5)

        self.gps_enabled = True
        self.gps_configured = True
        self._log("GPS CGNS enabled")
        return True

    def get_gnss_info(self) -> dict | None:
        """Get GPS data using AT+CGNSINFO (CGNS stack, full data).

        Returns:
            Dict with latitude, longitude, altitude, speed, course,
            satellites, pdop, gps_svs, glonass_svs, beidou_svs or None.
        """
        response = self.send_at("AT+CGNSINFO", timeout=3000)
        self._log(f"GPS raw: {response}")

        if "+CGNSINF:" not in response:
            return None

        data_start = response.rfind(":") + 1
        data = response[data_start:].strip()

        if not data:
            return None

        try:
            parts = data.split(",")

            run_status = parts[0].strip() if len(parts) > 0 else ""
            fix_status = parts[1].strip() if len(parts) > 1 else ""

            if run_status != "1" or fix_status != "1":
                return None

            lat_raw = parts[3].strip() if len(parts) > 3 else ""
            lat_dir = parts[4].strip() if len(parts) > 4 else ""
            lon_raw = parts[5].strip() if len(parts) > 5 else ""
            lon_dir = parts[6].strip() if len(parts) > 6 else ""

            if not lat_raw or not lon_dir:
                return None

            lat = self._convert_nmea_lat(lat_raw, lat_dir)
            lon = self._convert_nmea_lon(lon_raw, lon_dir)

            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return None

            alt = 0.0
            if len(parts) > 7 and parts[7].strip():
                try:
                    alt = float(parts[7].strip())
                except ValueError:
                    pass

            speed = 0.0
            if len(parts) > 8 and parts[8].strip():
                try:
                    speed = float(parts[8].strip())
                except ValueError:
                    pass

            course = 0.0
            if len(parts) > 9 and parts[9].strip():
                try:
                    course = float(parts[9].strip())
                except ValueError:
                    pass

            pdop = 0.0
            if len(parts) > 13 and parts[13].strip():
                try:
                    pdop = float(parts[13].strip())
                except ValueError:
                    pass

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

            return {
                "latitude": lat,
                "longitude": lon,
                "altitude": alt,
                "speed": speed,
                "course": course,
                "pdop": pdop,
                "satellites": gps_svs + glonass_svs + beidou_svs,
                "gps_svs": gps_svs,
                "glonass_svs": glonass_svs,
                "beidou_svs": beidou_svs,
            }

        except Exception as e:
            self._log(f"GPS parse error: {e}")
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
    def sync_time_from_network(self) -> bool:
        """Sync Pico system time from NTP.

        Returns:
            True if time was synced
        """
        try:
            import ntptime
            import machine

            ntptime.host = "pool.ntp.org"
            ntptime.settime()
            rtc = machine.RTC()
            dt = rtc.datetime()
            self._log(
                f"NTP synced: {dt[0]}-{dt[1]:02d}-{dt[2]:02d} {dt[4]:02d}:{dt[5]:02d}:{dt[6]:02d}"
            )
            return True
        except Exception as e:
            self._log(f"NTP sync failed: {e}")
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
        """Get GPS location with all data.

        Returns:
            Dict with GPS data or None
        """
        return self.sim.get_gnss_info()

    def sync_time(self) -> bool:
        """Sync time from network (NTP).

        Returns:
            True if synced
        """
        return self.sim.sync_time_from_network()
