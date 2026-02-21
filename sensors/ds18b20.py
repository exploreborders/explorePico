import time
from machine import Pin
from onewire import OneWire
from ds18x20 import DS18X20


class DS18B20:
    """DS18B20 temperature sensor driver with non-blocking conversion."""

    def __init__(self, pin_num: int) -> None:
        self.pin_num = pin_num
        self.pin = None
        self.ow = None
        self.ds = None
        self.roms = []
        self.last_value: float | None = None
        self._conversion_started = False
        self._conversion_start_time = 0

    def init(self) -> bool:
        """Initialize OneWire and DS18x20, scan for devices."""
        self.pin = Pin(self.pin_num)
        self.ow = OneWire(self.pin)
        self.ds = DS18X20(self.ow)

        self.roms = self.ds.scan()
        if self.roms:
            print(f"[DS18B20] Found {len(self.roms)} device(s) on GPIO{self.pin_num}")
            return True
        print(f"[DS18B20] No devices found on GPIO{self.pin_num}")
        return False

    def start_conversion(self) -> bool:
        """Start temperature conversion (non-blocking). Call read() after ~750ms."""
        if not self.ds or not self.roms or len(self.roms) == 0:
            return False

        try:
            self.ds.convert_temp()
            self._conversion_started = True
            self._conversion_start_time = time.ticks_ms()
            return True
        except Exception:
            return False

    def read(self, start_conversion: bool = True) -> float | None:
        """Read temperature in Celsius. Returns last known value on error.

        If start_conversion=True, starts a new conversion and returns last value.
        If start_conversion=False, reads the result of previous conversion.
        """
        if not self.ds or not self.roms or len(self.roms) == 0:
            return self.last_value

        if start_conversion:
            self.start_conversion()
            return self.last_value

        try:
            for rom in self.roms:
                temp = self.ds.read_temp(rom)
                if temp != 85.0:
                    self.last_value = round(temp, 1)
                    self._conversion_started = False
                    return self.last_value

            return self.last_value

        except Exception:
            self._conversion_started = False
            return self.last_value

    def get_last_value(self) -> float | None:
        """Get last known temperature value."""
        return self.last_value


class DS18B20Manager:
    """Wrapper for DS18B20 with auto-retry logic and hot-swap support."""

    def __init__(
        self, sensor: DS18B20, name: str, retry_interval_ms: int = 60000
    ) -> None:
        self.sensor = sensor
        self.name = name
        self.retry_interval_ms = retry_interval_ms
        self.initialized = False
        self.ever_connected = False
        self.conversion_start = 0
        self.last_retry = 0
        self.log_func = print

    def set_logger(self, logger) -> None:
        """Set custom logger function."""
        self.log_func = logger

    def read(self, conversion_time_ms: int = 750) -> float | None:
        """Read temperature with auto-retry logic."""
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
                self.sensor.start_conversion()
                self.conversion_start = time.ticks_ms()
                return self.sensor.get_last_value()
            return None

        if self.conversion_start == 0:
            self.sensor.start_conversion()
            self.conversion_start = time.ticks_ms()
            return self.sensor.get_last_value()

        elapsed = time.ticks_diff(now, self.conversion_start)
        if elapsed >= conversion_time_ms:
            temp = self.sensor.read(start_conversion=False)
            if temp is not None:
                self.sensor.start_conversion()
                self.conversion_start = time.ticks_ms()
                return temp
            else:
                self.log_func(self.name, "Sensor disconnected")
                self.initialized = False
                self.last_retry = 0
                return None

        return self.sensor.get_last_value()
