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
        if not self.ds or not self.roms:
            return False

        try:
            self.ds.convert_temp()
            self._conversion_started = True
            self._conversion_start_time = time.ticks_ms()
            return True
        except Exception as e:
            print(f"[DS18B20] Start conversion error: {e}")
            return False

    def is_conversion_ready(self) -> bool:
        """Check if conversion is ready (750ms elapsed)."""
        if not self._conversion_started:
            return False
        elapsed = time.ticks_diff(time.ticks_ms(), self._conversion_start_time)
        return elapsed >= 750

    def read(self, start_conversion: bool = True) -> float | None:
        """Read temperature in Celsius. Returns last known value on error.

        If start_conversion=True, starts a new conversion and returns last value.
        If start_conversion=False, reads the result of previous conversion.
        """
        if not self.ds or not self.roms:
            if start_conversion:
                self.start_conversion()
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

        except Exception as e:
            print(f"[DS18B20] Read error: {e}")
            self._conversion_started = False
            return self.last_value

    def read_blocking(self) -> float | None:
        """Blocking read - starts conversion and waits for result."""
        self.start_conversion()
        time.sleep_ms(750)
        return self.read(start_conversion=False)

    def get_last_value(self) -> float | None:
        """Get last known temperature value."""
        return self.last_value
