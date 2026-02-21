import time
from machine import Pin, SPI


class ISNS20:
    """Pmod ISNS20 current sensor driver using SPI."""

    def __init__(self, cs_pin: int, spi_port: int = 0) -> None:
        self.cs_pin_num = cs_pin
        self.spi_port = spi_port
        self.cs = None
        self.spi = None
        self.last_value: float | None = None
        self._initialized = False
        self._raw_buffer = []
        self._buffer_size = 10

    def init(self) -> bool:
        """Initialize SPI and verify sensor communication."""
        try:
            self.cs = Pin(self.cs_pin_num, Pin.OUT, value=1)

            if self.spi_port == 0:
                self.spi = SPI(
                    0,
                    baudrate=1_000_000,
                    polarity=0,
                    phase=1,
                    bits=8,
                    firstbit=SPI.MSB,
                    sck=Pin(2),
                    mosi=Pin(3),
                    miso=Pin(4),
                )
            else:
                self.spi = SPI(
                    1,
                    baudrate=1_000_000,
                    polarity=0,
                    phase=1,
                    bits=8,
                    firstbit=SPI.MSB,
                    sck=Pin(10),
                    mosi=Pin(11),
                    miso=Pin(12),
                )

            test_read = self._read_raw()
            if test_read is not None:
                self._initialized = True
                print(f"[ISNS20] Initialized on CS pin GP{self.cs_pin_num}")
                return True

            print("[ISNS20] No response from sensor")
            return False

        except Exception as e:
            print(f"[ISNS20] Init failed: {e}")
            return False

    def _read_raw(self) -> int | None:
        """Read raw 12-bit ADC value from sensor."""
        if not self.spi or not self.cs:
            return None

        try:
            self.cs.value(0)
            time.sleep_us(1)

            data = self.spi.read(2)

            time.sleep_us(1)
            self.cs.value(1)

            if len(data) == 2:
                raw = ((data[0] & 0x0F) << 8) | data[1]
                raw = raw & 0xFFF
                return raw

            return None

        except Exception as e:
            print(f"[ISNS20] Read error: {e}")
            return None

        try:
            self.cs.value(0)
            time.sleep_us(1)

            data = self.spi.read(2)

            time.sleep_us(1)
            self.cs.value(1)

            if len(data) == 2:
                raw = ((data[0] & 0x0F) << 8) | data[1]
                raw = raw & 0xFFF
                print(
                    f"[ISNS20] Raw ADC: {raw} = {raw * 3.3 / 4095:.3f}V, bytes: {data[0]:02x} {data[1]:02x}"
                )
                return raw

            return None

        except Exception as e:
            print(f"[ISNS20] Read error: {e}")
            return None

        try:
            self.cs.value(0)
            time.sleep_us(2)

            self.spi.write(b"\x00")
            data = self.spi.read(2)

            time.sleep_us(2)
            self.cs.value(1)

            if len(data) == 2:
                raw = (data[1] << 8) | data[0]
                raw = raw >> 4
                raw = raw & 0xFFF
                print(
                    f"[ISNS20] Raw ADC: {raw} = {raw * 3.3 / 4095:.3f}V, bytes: {data[0]:02x} {data[1]:02x}"
                )
                return raw

            return None

        except Exception as e:
            print(f"[ISNS20] Read error: {e}")
            return None

        try:
            self.cs.value(0)
            time.sleep_us(2)

            data = self.spi.read(2)

            time.sleep_us(2)
            self.cs.value(1)

            if len(data) == 2:
                raw = (data[0] << 8) | data[1]
                raw = raw >> 4
                raw = raw & 0xFFF
                print(
                    f"[ISNS20] Raw ADC: {raw} = {raw * 3.3 / 4095:.3f}V, bytes: {data[0]:02x} {data[1]:02x}"
                )
                return raw

            return None

        except Exception as e:
            print(f"[ISNS20] Read error: {e}")
            return None

    def read_current(self) -> float | None:
        """Read current in Amperes with moving average filter."""
        raw = self._read_raw()

        if raw is None:
            return self.last_value

        self._raw_buffer.append(raw)
        if len(self._raw_buffer) > self._buffer_size:
            self._raw_buffer.pop(0)

        avg_raw = sum(self._raw_buffer) // len(self._raw_buffer)

        try:
            voltage = (avg_raw / 4095.0) * 3.3

            sensitivity = 0.066
            offset_voltage = 1.65

            current = (voltage - offset_voltage) / sensitivity
            current = round(current, 1)

            self.last_value = current
            return current

        except Exception as e:
            print(f"[ISNS20] Calc error: {e}")
            return self.last_value

        try:
            voltage = (raw / 4095.0) * 3.3

            sensitivity = 0.066
            offset_voltage = 1.65

            current = (voltage - offset_voltage) / sensitivity
            current = round(current, 1)

            print(
                f"[ISNS20] Raw: {raw}, Voltage: {voltage:.3f}V, Current: {current:.2f}A"
            )

            self.last_value = current
            return current

        except Exception as e:
            print(f"[ISNS20] Calc error: {e}")
            return self.last_value

    def get_last_value(self) -> float | None:
        """Get last known current value."""
        return self.last_value

    def is_initialized(self) -> bool:
        """Check if sensor is initialized."""
        return self._initialized


class ISNS20Manager:
    """Wrapper for ISNS20 with auto-retry logic."""

    def __init__(
        self, sensor: ISNS20, name: str, retry_interval_ms: int = 60000
    ) -> None:
        self.sensor = sensor
        self.name = name
        self.retry_interval_ms = retry_interval_ms
        self.initialized = False
        self.ever_connected = False
        self.last_retry = 0
        self.log_func = print

    def set_logger(self, logger) -> None:
        """Set custom logger function."""
        self.log_func = logger

    def read(self) -> float | None:
        """Read current with auto-retry logic."""
        now = time.ticks_ms()

        if not self.initialized:
            should_retry = self.last_retry == 0
            if not should_retry:
                elapsed = time.ticks_diff(now, self.last_retry)
                should_retry = elapsed >= self.retry_interval_ms

            if should_retry:
                self.log_func(self.name, "Initializing...")
                self.initialized = self.sensor.init()

                if not self.initialized:
                    self.last_retry = now
                    self.log_func(
                        self.name,
                        f"Init failed! Retrying in {self.retry_interval_ms // 1000}s...",
                    )
                    return None

                self.ever_connected = True
                self.last_retry = now
                self.log_func(self.name, "Initialized successfully")
                return self.sensor.read_current()

            return None

        current = self.sensor.read_current()

        if current is not None:
            return current

        self.log_func(self.name, "Sensor disconnected")
        self.initialized = False
        self.last_retry = 0
        return None

    def get_last_value(self) -> float | None:
        """Get last known current value."""
        return self.sensor.get_last_value()

    def is_connected(self) -> bool:
        """Check if sensor is currently connected."""
        return self.initialized and self.sensor.is_initialized()
