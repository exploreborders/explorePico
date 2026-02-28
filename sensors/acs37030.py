"""
ACS37030 Current Sensor Driver for Pico 2W

Hardware:
    - Sensor: Allegro ACS37030LLZATR-020B3 (±20A bidirectional)
    - Interface: Analog voltage output
    - ADC: ADS1115 (I2C) or Pico built-in ADC

Features:
    - Bidirectional current measurement (±20A)
    - High bandwidth (DC to 5MHz)
    - Galvanically isolated
    - Moving average filter

Technical (ACS37030LLZATR-020B3):
    - Sensitivity: 66 mV/A
    - Zero point: 1.65V (at 0A)
    - Output range: 0.33V (-20A) to 2.97V (+20A)
    - Supply: 3.0V - 3.6V (3.3V typical)

Calculation:
    VOUT = 1.65V + (0.066 V/A) × Current
    Current = (VOUT - 1.65V) / 0.066

Wiring (ADS1115):
    ACS37030 VOUT ──► ADS1115 A0-A3
    ACS37030 VDD   ──► 3.3V
    ACS37030 GND   ──► GND

Wiring (Pico ADC):
    ACS37030 VOUT ──► ADC0 (GP26)
    ACS37030 VDD   ──► 3.3V
    ACS37030 GND   ──► GND

Usage:
    from sensors.acs37030 import ACS37030, ACS37030Manager
    from config import ACS37030_SENSITIVITY, ACS37030_ZERO_POINT

    sensor = ACS37030(adc, channel=0)
    manager = ACS37030Manager(sensor, "ACS37030", retry_interval_ms=60000)

    current = manager.read()
    if current is not None:
        print(f"Current: {current}A")

Notes:
    - Requires ADS1115 for multiple sensors (channels 0-3)
    - For 5th sensor, use Pico's built-in ADC (GP26)
    - 85.0°C reading is invalid (sensor disconnected) - not applicable for current
    - Use moving average for stable readings
"""

import time


class ACS37030:
    """ACS37030 current sensor driver using ADS1115 or Pico ADC."""

    def __init__(
        self,
        adc,
        channel: int,
        sensitivity: float = 0.066,
        zero_point: float = 1.65,
        is_pico_adc: bool = False,
    ) -> None:
        """Initialize ACS37030 sensor.

        Args:
            adc: ADS1115 instance or Pico ADC instance
            channel: ADC channel (0-3 for ADS1115)
            sensitivity: Volts per Amp (0.066 for ±20A version)
            zero_point: Voltage at zero current (1.65V for bidirectional)
            is_pico_adc: True if using Pico built-in ADC
        """
        self.adc = adc
        self.channel = channel
        self.sensitivity = sensitivity
        self.zero_point = zero_point
        self.is_pico_adc = is_pico_adc
        self.last_value: float | None = None

    def read_voltage(self) -> float | None:
        """Read voltage from ADC.

        Returns:
            Voltage in volts, or None on error
        """
        try:
            if self.is_pico_adc:
                reading = self.adc.read_u16()
                voltage = reading * 3.3 / 65535
                return voltage
            else:
                return self.adc.read_voltage(self.channel)
        except Exception:
            return None

    def read_current(self) -> float | None:
        """Read current value in Amps.

        Returns:
            Current in Amps, or None on error
        """
        voltage = self.read_voltage()

        if voltage is None:
            return None

        current = (voltage - self.zero_point) / self.sensitivity
        self.last_value = current
        return round(current, 2)

    def init(self) -> bool:
        """Initialize and verify sensor.

        Returns:
            True if sensor responds, False otherwise
        """
        voltage = self.read_voltage()
        if voltage is not None:
            return True
        return False


class ACS37030Manager:
    """Manages ACS37030 sensors with retry logic and filtering."""

    def __init__(
        self,
        sensor: ACS37030,
        name: str = "ACS37030",
        retry_interval_ms: int = 60000,
    ) -> None:
        """Initialize sensor manager.

        Args:
            sensor: ACS37030 instance
            name: Sensor name for logging
            retry_interval_ms: Retry interval for failed init
        """
        self.sensor = sensor
        self.name = name
        self.retry_interval_ms = retry_interval_ms

        self._logger = None
        self._last_init = 0
        self._initialized = False
        self._ever_connected = False

        self._raw_buffer = []
        self._buffer_size = 10

    def set_logger(self, logger) -> None:
        """Set logging function.

        Args:
            logger: Logging function with signature (tag, message)
        """
        self._logger = logger

    def _log(self, message: str) -> None:
        """Log message if logger is set."""
        if self._logger:
            self._logger(self.name, message)
        else:
            print(f"[{self.name}] {message}")

    def init(self) -> bool:
        """Initialize sensor with retry logic.

        Returns:
            True if initialization successful
        """
        now = time.ticks_ms()

        if self._initialized:
            return True

        if time.ticks_diff(now, self._last_init) < self.retry_interval_ms:
            return False

        self._last_init = now

        if self.sensor.init():
            self._initialized = True
            self._ever_connected = True
            self._log("Initialized successfully")
            return True

        self._log("Init failed! Retrying...")
        return False

    def read(self) -> float | None:
        """Read current value with moving average filter.

        Returns:
            Filtered current in Amps, or None if not initialized
        """
        if not self.init():
            return self.sensor.last_value

        raw_value = self.sensor.read_current()

        if raw_value is None:
            return self.sensor.last_value

        self._raw_buffer.append(raw_value)

        if len(self._raw_buffer) > self._buffer_size:
            self._raw_buffer.pop(0)

        filtered = sum(self._raw_buffer) / len(self._raw_buffer)
        return round(filtered, 2)

    @property
    def ever_connected(self) -> bool:
        """Check if sensor was ever connected."""
        return self._ever_connected

    @property
    def is_initialized(self) -> bool:
        """Check if sensor is currently initialized."""
        return self._initialized
