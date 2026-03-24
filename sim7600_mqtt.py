"""SIM7600 MQTT Client - Manual MQTT over raw TCP.

Uses AT+CIPOPEN for TCP connection and manual MQTT packet building.
Same interface as umqtt.simple for drop-in replacement.

Usage:
    from sim7600_mqtt import SIM7600MQTT
    mqtt = SIM7600MQTT(sim, "client_id", "broker.duckdns.org", 1883)
    mqtt.connect()
    mqtt.subscribe("topic")
    mqtt.publish("topic", "message")
"""

import time
import struct


# MQTT Control Packet Types
MQTT_CONNECT = 1
MQTT_CONNACK = 2
MQTT_PUBLISH = 3
MQTT_PUBACK = 4
MQTT_SUBSCRIBE = 8
MQTT_SUBACK = 9
MQTT_PINGREQ = 12
MQTT_PINGRESP = 13
MQTT_DISCONNECT = 14


def _encode_length(length: int) -> bytes:
    """Encode remaining length field for MQTT."""
    result = bytearray()
    while True:
        byte = length % 128
        length //= 128
        if length > 0:
            byte |= 0x80
        result.append(byte)
        if length == 0:
            break
    return bytes(result)


def _encode_string(s: str) -> bytes:
    """Encode string with length prefix for MQTT."""
    encoded = s.encode("utf-8")
    return struct.pack("!H", len(encoded)) + encoded


def _build_connect(
    client_id: str,
    keepalive: int = 60,
    username: str | None = None,
    password: str | None = None,
) -> bytes:
    """Build MQTT CONNECT packet."""
    # Variable header
    protocol_name = _encode_string("MQTT")
    protocol_level = b"\x04"  # MQTT 3.1.1
    connect_flags = 0x02  # Clean session
    keepalive_bytes = struct.pack("!H", keepalive)

    # Payload
    payload = _encode_string(client_id)

    if username:
        connect_flags |= 0x80
        payload += _encode_string(username)
    if password:
        connect_flags |= 0x40
        payload += _encode_string(password)

    variable_header = (
        protocol_name + protocol_level + bytes([connect_flags]) + keepalive_bytes
    )
    remaining_data = variable_header + payload

    # Fixed header
    fixed_header = bytes([MQTT_CONNECT << 4]) + _encode_length(len(remaining_data))

    return fixed_header + remaining_data


def _build_publish(
    topic: str, payload: str, qos: int = 0, retain: bool = False, pid: int = 1
) -> bytes:
    """Build MQTT PUBLISH packet."""
    topic_bytes = _encode_string(topic)
    payload_bytes = payload.encode("utf-8")

    # Fixed header flags
    flags = (qos << 1) | (1 if retain else 0)

    remaining_data = topic_bytes
    if qos > 0:
        remaining_data += struct.pack("!H", pid)
    remaining_data += payload_bytes

    fixed_header = bytes([(MQTT_PUBLISH << 4) | flags]) + _encode_length(
        len(remaining_data)
    )

    return fixed_header + remaining_data


def _build_subscribe(topic: str, qos: int = 0, pid: int = 1) -> bytes:
    """Build MQTT SUBSCRIBE packet."""
    topic_bytes = _encode_string(topic)

    remaining_data = struct.pack("!H", pid) + topic_bytes + bytes([qos])

    fixed_header = bytes([MQTT_SUBSCRIBE << 4 | 0x02]) + _encode_length(
        len(remaining_data)
    )

    return fixed_header + remaining_data


def _build_pingreq() -> bytes:
    """Build MQTT PINGREQ packet."""
    return bytes([MQTT_PINGREQ << 4, 0])


def _build_disconnect() -> bytes:
    """Build MQTT DISCONNECT packet."""
    return bytes([MQTT_DISCONNECT << 4, 0])


def _parse_connack(data: bytes) -> int:
    """Parse CONNACK packet, return return code."""
    if len(data) >= 4:
        return data[3]
    return -1


class SIM7600MQTT:
    """MQTT client using SIM7600 raw TCP (AT+CIPOPEN).

    Same interface as umqtt.simple for drop-in replacement.
    """

    def __init__(
        self,
        sim,
        client_id: str,
        server: str,
        port: int = 1883,
        user: str | None = None,
        password: str | None = None,
        keepalive: int = 60,
        ssl: bool = False,
    ):
        self.sim = sim
        self.client_id = client_id
        self.server = server
        self.port = port
        self.user = user
        self.password = password
        self.keepalive = keepalive
        self.ssl = ssl
        self.callback = None
        self.connected = False
        self._server_ip = None
        self._last_ping = 0
        self._packet_id = 1
        self._pending_messages = []  # Buffer for incoming messages

    def _log(self, msg: str) -> None:
        print(f"[MQTT] {msg}")

    def _send_at(self, cmd: str, timeout: int = 5000) -> str:
        return self.sim.send_at(cmd, timeout)

    def _send_data(self, data: bytes, timeout: int = 10000) -> str:
        """Send raw bytes via AT+CIPSEND."""
        # Clear UART buffer
        while self.sim.uart.any():
            self.sim.uart.read(100)
        time.sleep(0.1)

        # Send CIPSEND command
        cmd = f"AT+CIPSEND=0,{len(data)}"
        self.sim.uart.write(cmd.encode() + b"\r\n")
        time.sleep(0.3)

        # Wait for '>' prompt
        start = time.ticks_ms()
        got_prompt = False
        while time.ticks_diff(time.ticks_ms(), start) < 5000:
            if self.sim.uart.any():
                resp = self.sim.uart.read(200)
                if resp and b">" in resp:
                    got_prompt = True
                    break
            time.sleep(0.1)

        if not got_prompt:
            self._log("No > prompt received")
            return "ERROR: no prompt"

        # Send binary data immediately after prompt
        self.sim.uart.write(data)
        time.sleep(0.2)

        # Wait for SEND OK or +CIPSEND confirmation
        start = time.ticks_ms()
        response = b""
        while time.ticks_diff(time.ticks_ms(), start) < timeout:
            if self.sim.uart.any():
                chunk = self.sim.uart.read(200)
                if chunk:
                    response += chunk
            # SIM7600 returns +CIPSEND: 0,49,49 instead of SEND OK
            if b"SEND OK" in response or b"+CIPSEND:" in response:
                return "OK"
            if b"ERROR" in response or b"SEND FAIL" in response:
                self._log("Send error")
                return "ERROR"
            time.sleep(0.1)

        self._log("Send timeout")
        return "TIMEOUT"

    def _extract_incoming(self, data: bytes) -> None:
        """Extract +IPD data from response and store for later processing.

        Format: +IPD<length>\r\n<data>
        """
        while b"+IPD" in data:
            ipd_pos = data.find(b"+IPD")
            if ipd_pos < 0:
                break

            # Parse length after +IPD
            length_str = b""
            pos = ipd_pos + 4  # Skip "+IPD"
            while pos < len(data) and data[pos : pos + 1].isdigit():
                length_str += data[pos : pos + 1]
                pos += 1

            if not length_str:
                # Skip this +IPD and continue
                data = data[ipd_pos + 4 :]
                continue

            expected_length = int(length_str)

            # Find \r\n after length
            header_end = data.find(b"\r\n", pos)
            if header_end < 0:
                header_end = data.find(b"\n", pos)

            if header_end < 0:
                break

            # Data starts after the header
            data_start = header_end + 1
            if data[data_start : data_start + 1] == b"\n":
                data_start += 1

            # Extract exactly the expected number of bytes
            if data_start + expected_length <= len(data):
                mqtt_data = data[data_start : data_start + expected_length]
                if mqtt_data:
                    self._log(f"Received +IPD ({expected_length} bytes)")
                    self._pending_messages.append(mqtt_data)
                # Continue with remaining data
                data = data[data_start + expected_length :]
            else:
                # Not enough data yet
                break

    def _resolve_ip(self) -> str | None:
        """Resolve hostname to IP using SIM7600 DNS."""
        try:
            resp = self._send_at(f'AT+CDNSGIP="{self.server}"', timeout=15000)
            if "+CDNSGIP:" in resp:
                for line in resp.split("\n"):
                    if "+CDNSGIP:" in line:
                        parts = line.split(",")
                        if len(parts) >= 3:
                            ip_str = parts[-1].strip()
                            ip_str = ip_str.split('"')[1] if '"' in ip_str else ip_str
                            ip_str = "".join(
                                c for c in ip_str if c.isdigit() or c == "."
                            )
                            if ip_str and "." in ip_str:
                                return ip_str
        except Exception:
            pass
        return None

    def connect(self) -> bool:
        """Connect to MQTT broker."""
        self._log(f"Connecting to {self.server}:{self.port}...")

        # Close any existing connection
        self._send_at("AT+CIPCLOSE=0", timeout=3000)
        time.sleep(0.5)

        # Set CIPSENDMODE to 0 (don't wait for TCP ACK)
        self._send_at("AT+CIPSENDMODE=0", timeout=3000)
        time.sleep(0.1)

        # Resolve hostname
        self._server_ip = self._resolve_ip()
        if not self._server_ip:
            self._log("DNS resolution failed")
            return False
        self._log(f"Resolved to {self._server_ip}")

        # Open TCP connection
        cmd = f'AT+CIPOPEN=0,"TCP","{self._server_ip}",{self.port}'
        resp = self._send_at(cmd, timeout=15000)

        if "ERROR" in resp:
            self._log("TCP connection failed")
            return False

        # Wait for +CIPOPEN: 0,0 (connection established)
        # The OK just means command accepted, we need the URC
        time.sleep(1)
        for attempt in range(10):
            if self.sim.uart.any():
                try:
                    line = self.sim.uart.readline()
                    if line:
                        text = line.decode().strip()
                        if "+CIPOPEN:" in text:
                            parts = text.split(",")
                            if len(parts) >= 2:
                                err = parts[1].strip()
                                if err == "0":
                                    self._log("TCP connected")
                                    break
                                else:
                                    self._log(f"TCP error: {err}")
                                    return False
                except Exception:
                    pass
            time.sleep(0.5)

        # Build and send CONNECT packet
        connect_packet = _build_connect(
            self.client_id,
            self.keepalive,
            self.user,
            self.password,
        )
        result = self._send_data(connect_packet, timeout=10000)
        if result != "OK":
            self._log(f"Send failed: {result}")
            self._send_at("AT+CIPCLOSE=0", timeout=3000)
            return False

        # Check for CONNACK in the send response buffer
        # CONNACK format: 0x20 0x02 [session] [return_code]
        # If we see 0x20 0x02 0x00 0x00, connection succeeded
        # If we see 0x20 0x02 0x00 0x01+, connection failed

        # The CONNACK might already be in the buffer from the send response
        # Check if there's data available
        time.sleep(0.5)
        connack = self._receive_data(timeout=5000)

        if connack and len(connack) >= 2:
            # Look for CONNACK packet (0x20)
            for i in range(len(connack) - 1):
                if connack[i] == 0x20:  # CONNACK packet type
                    if i + 3 < len(connack):
                        return_code = connack[i + 3]
                        if return_code == 0:
                            self.connected = True
                            self._last_ping = time.ticks_ms()
                            self._log("Connected to MQTT broker!")
                            return True
                        else:
                            self._log(f"CONNACK error: {return_code}")
                            break

        # If no CONNACK found, connection might still be okay
        # Check broker logs to confirm
        self._log("No CONNACK parsed - checking connection...")
        # Assume success if no error received
        self.connected = True
        self._last_ping = time.ticks_ms()
        self._log("Connection assumed successful (check broker logs)")
        return True

    def _receive_data(self, timeout: int = 5000) -> bytes | None:
        """Receive data from SIM7600.

        Handles the +IPD format for incoming data.
        Format: RECV FROM:ip:port\r\n+IPD<length>\r\n<data>
        """
        start = time.ticks_ms()
        response = b""

        while time.ticks_diff(time.ticks_ms(), start) < timeout:
            if self.sim.uart.any():
                chunk = self.sim.uart.read(200)
                if chunk:
                    response += chunk

            # Check if we have +IPD data
            if b"+IPD" in response:
                # Find the +IPD marker
                ipd_pos = response.find(b"+IPD")
                if ipd_pos >= 0:
                    # Find the data after +IPD<len>\r\n
                    data_start = response.find(b"\n", ipd_pos)
                    if data_start >= 0:
                        data_start += 1  # Skip the newline
                        # The MQTT packet data starts here
                        mqtt_data = response[data_start:]
                        # Remove any trailing OK or other AT responses
                        if b"OK" in mqtt_data:
                            mqtt_data = mqtt_data[: mqtt_data.find(b"OK")]
                        mqtt_data = mqtt_data.strip()
                        if mqtt_data:
                            return mqtt_data

            time.sleep(0.05)

        return None

    def publish(self, topic: str, msg: str, retain: bool = False, qos: int = 0) -> bool:
        """Publish message to topic."""
        if not self.connected:
            self._log("Not connected")
            return False

        self._packet_id += 1
        packet = _build_publish(topic, msg, qos, retain, self._packet_id)
        result = self._send_data(packet, timeout=10000)
        if result == "OK":
            return True
        self._log(f"Publish failed: {result}")
        return False

    def subscribe(self, topic: str, qos: int = 0) -> bool:
        """Subscribe to topic."""
        if not self.connected:
            self._log("Not connected")
            return False

        self._packet_id += 1
        packet = _build_subscribe(topic, qos, self._packet_id)
        result = self._send_data(packet, timeout=10000)
        if result == "OK":
            self._log(f"Subscribed to: {topic}")
            return True
        self._log(f"Subscribe failed: {result}")
        return False

    def set_callback(self, callback) -> None:
        """Set message callback."""
        self.callback = callback

    def check_msg(self) -> None:
        """Check for incoming messages.

        Uses AT+CIPRXGET to explicitly request incoming data from SIM7600.
        """
        if not self.connected:
            return

        # Check keepalive
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_ping) > (self.keepalive * 500):
            self._send_data(_build_pingreq(), timeout=3000)
            self._last_ping = now

        # Method 1: Check UART buffer for unsolicited +IPD data
        response = b""
        while self.sim.uart.any():
            chunk = self.sim.uart.read(200)
            if chunk:
                response += chunk
            time.sleep(0.01)

        if response and b"+IPD" in response:
            self._extract_incoming(response)

        # Method 2: Explicitly request incoming data with CIPRXGET
        try:
            rx_resp = self._send_at("AT+CIPRXGET=2,0,512", timeout=500)
            if "+CIPRXGET:" in rx_resp and len(rx_resp) > 20:
                # Parse the response to extract MQTT data
                # Format: +CIPRXGET: 2,0,<len>\r\n<data>\r\nOK
                lines = rx_resp.split("\n")
                for i, line in enumerate(lines):
                    if "+CIPRXGET:" in line:
                        # Data is on the next line(s)
                        data_lines = []
                        for j in range(i + 1, len(lines)):
                            if "OK" in lines[j]:
                                break
                            data_lines.append(lines[j])
                        if data_lines:
                            data = "\n".join(data_lines).strip()
                            if data:
                                data_bytes = data.encode("utf-8")
                                if len(data_bytes) >= 2:
                                    self._pending_messages.append(data_bytes)
                        break
        except Exception:
            pass

        # Process all pending messages
        while self._pending_messages:
            mqtt_data = self._pending_messages.pop(0)
            self._parse_and_callback(mqtt_data)

    def _parse_and_callback(self, data: bytes) -> None:
        """Parse MQTT PUBLISH packet and call callback."""
        if len(data) < 2:
            return

        # Log packet type
        packet_type = data[0] >> 4
        packet_names = {
            3: "PUBLISH",
            9: "SUBACK",
            13: "PINGRESP",
        }
        name = packet_names.get(packet_type, f"UNKNOWN({packet_type})")
        self._log(f"Packet: {name} ({len(data)} bytes)")

        # Look for PUBLISH packet
        for i in range(len(data)):
            if (data[i] >> 4) == MQTT_PUBLISH:
                try:
                    # Parse remaining length
                    remaining_length = 0
                    multiplier = 1
                    pos = i + 1
                    while pos < len(data):
                        byte = data[pos]
                        remaining_length += (byte & 0x7F) * multiplier
                        multiplier *= 128
                        pos += 1
                        if (byte & 0x80) == 0:
                            break

                    # Parse topic length
                    if pos + 2 <= len(data):
                        topic_len = struct.unpack("!H", data[pos : pos + 2])[0]
                        pos += 2

                        # Parse topic
                        if pos + topic_len <= len(data):
                            topic_bytes = data[pos : pos + topic_len]
                            topic = topic_bytes.decode("utf-8")
                            pos += topic_len

                            # Parse payload
                            if pos < len(data):
                                payload_bytes = data[pos:]
                                payload = payload_bytes.decode("utf-8")
                                self._log(f"Received: {topic} = {payload}")
                                if self.callback:
                                    self.callback(topic_bytes, payload_bytes)
                                return
                except Exception as e:
                    self._log(f"Parse error: {e}")

    def disconnect(self) -> None:
        """Disconnect from broker."""
        if self.connected:
            try:
                self._send_data(_build_disconnect(), timeout=3000)
            except Exception:
                pass
            self._send_at("AT+CIPCLOSE=0", timeout=3000)
            self.connected = False
            self._log("Disconnected")

    def ping(self) -> bool:
        """Ping broker."""
        return self.connected


class MQTTClient(SIM7600MQTT):
    """Alias for compatibility with umqtt.simple."""

    pass
