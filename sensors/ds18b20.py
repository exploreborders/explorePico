"""
DS18B20 Temperature Sensor Driver for Pico 2W

Hardware:
    - Sensor: DS18B20 one-wire digital temperature sensor
    - Pin: GPIO22 (configurable via DS18B20_PIN in config.py)
    - Power: Parasitic power or external 3.3V/5V
    - Bus: One-wire communication protocol
    - Max sensors: ~10 on single bus (practical limit)

Features:
    - Multi-sensor support (automatic detection)
    - Non-blocking conversion (doesn't block main loop)
    - Hot-swap support (detects sensors added/removed)
    - 85°C filter (power-on reset value)

Technical:
    - Resolution: 9-12 bits (configurable)
    - Conversion time: 94ms (9-bit) to 750ms (12-bit)
    - Accuracy: ±0.5°C from -10°C to +85°C
    - Range: -55°C to +125°C

Usage:
    from sensors import DS18B20, DS18B20Manager
    from config import DS18B20_PIN, TEMP_CONVERSION_TIME_MS

    # Create sensor and manager
    sensor = DS18B20(DS18B20_PIN)
    manager = DS18B20Manager(sensor, "DS18B20", retry_interval_ms=60000)

    # In main loop
    temps = manager.read(TEMP_CONVERSION_TIME_MS)
    if temps:
        for temp in temps:
            print(f"Temperature: {temp}°C")

Notes:
    - Multiple sensors auto-detected on same pin
    - First sensor = room temperature (index 0)
    - Second sensor = water temperature (index 1)
    - Uses non-blocking pattern: start_conversion() then read() after delay
"""

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
        self.last_values: list[float | None] = []
        self._conversion_started = False
        self._conversion_start_time = 0
        self._logger = print  # Default to print, can be overridden

    def set_logger(self, logger) -> None:
        """Set custom logger function."""
        self._logger = logger

    def _log(self, message: str) -> None:
        """Log message using configured logger."""
        self._logger("DS18B20", message)

    def init(self) -> bool:
        """Initialize OneWire and DS18x20, scan for devices."""
        self.pin = Pin(self.pin_num)
        self.ow = OneWire(self.pin)
        self.ds = DS18X20(self.ow)

        self.roms = self.ds.scan()
        if self.roms:
            self.last_values = [None] * len(self.roms)
            self._log(f"Found {len(self.roms)} device(s) on GPIO{self.pin_num}")
            return True
        self._log(f"No devices found on GPIO{self.pin_num}")
        return False

    def start_conversion(self) -> bool:
        """Start temperature conversion (non-blocking)."""
        if not self.ds or not self.roms or len(self.roms) == 0:
            return False

        try:
            self.ds.convert_temp()
            self._conversion_started = True
            self._conversion_start_time = time.ticks_ms()
            return True
        except Exception:
            return False

    def read(self, start_conversion: bool = True) -> list[float | None]:
        """Read all temperatures in Celsius. Returns list of temperatures."""
        if not self.ds or not self.roms or len(self.roms) == 0:
            return self.last_values

        if start_conversion:
            self.start_conversion()
            return self.last_values

        try:
            for i, rom in enumerate(self.roms):
                temp = self.ds.read_temp(rom)
                if temp != 85.0:
                    self.last_values[i] = round(temp, 1)

            self._conversion_started = False
            return self.last_values

        except Exception:
            self._conversion_started = False
            return self.last_values

    def get_last_values(self) -> list[float | None]:
        """Get last known temperature values."""
        return self.last_values

    def get_last_value(self) -> float | None:
        """Get last known temperature (for single sensor compatibility)."""
        if self.last_values:
            return self.last_values[0]
        return None


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
        # Also pass logger to the underlying sensor
        if hasattr(self.sensor, "set_logger"):
            self.sensor.set_logger(logger)

    def read(self, conversion_time_ms: int = 750) -> list[float | None]:
        """Read temperatures from all sensors. Returns list of temperatures."""
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
                num_sensors = len(self.sensor.roms)
                self.log_func(self.name, f"Initialized with {num_sensors} sensor(s)")
                self.sensor.start_conversion()
                self.conversion_start = time.ticks_ms()
                return self.sensor.get_last_values()
            return None

        if self.conversion_start == 0:
            self.sensor.start_conversion()
            self.conversion_start = time.ticks_ms()
            return self.sensor.get_last_values()

        elapsed = time.ticks_diff(now, self.conversion_start)
        if elapsed >= conversion_time_ms:
            temps = self.sensor.read(start_conversion=False)
            if temps:
                self.sensor.start_conversion()
                self.conversion_start = time.ticks_ms()
                return temps
            else:
                self.log_func(self.name, "Sensor(s) disconnected")
                self.initialized = False
                self.last_retry = 0
                return None

        return self.sensor.get_last_values()
