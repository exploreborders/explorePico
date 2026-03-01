"""
ADS1115 16-Bit ADC Driver for Pico 2W

Hardware:
    - ADC: ADS1115 (16-bit resolution)
    - Interface: I2C
    - Address: 0x48-0x4B (default 0x48)
    - Channels: 4 single-ended or 2 differential

Features:
    - 16-bit resolution (65536 levels)
    - Programmable gain amplifier (PGA)
    - Configurable sample rate
    - Continuous or single-shot conversion

Technical:
    - Supply: 2.0V - 5.5V
    - I2C Speed: up to 3.4MHz
    - Low current consumption: 150µA

Register Map:
    - 0x00: Conversion Register (READ)
    - 0x01: Config Register (READ/WRITE)
    - 0x02: Lo_thresh Register
    - 0x03: Hi_thresh Register

Config Register Bits:
    - Bit 15: OS (Operational Status/Single-Shot Start)
    - Bits 14-12: MUX (Input Multiplexer)
    - Bits 11-9: PGA (Programmable Gain)
    - Bit 8: MODE (Single-shot/Continuous)
    - Bits 7-5: DR (Data Rate)
    - Bit 4: COMP_MODE (Comparator Mode)
    - Bit 3: COMP_POL (Comparator Polarity)
    - Bit 2: COMP_LAT (Latching Comparator)
    - Bits 1-0: COMP_QUE (Comparator Queue)

Usage:
    from sensors.ads1115 import ADS1115
    adc = ADS1115(address=0x48, scl_pin=5, sda_pin=4)
    voltage = adc.read_voltage(0)  # Read channel 0

Notes:
    - Requires machine.I2C peripheral
    - Default address 0x48 (ADDR pin to GND)
    - Use set_gain() to adjust measurement range
"""

import time
from machine import I2C, Pin


class ADS1115:
    """ADS1115 16-bit ADC driver via I2C."""

    I2C_ADDRESS = 0x48

    REG_CONVERSION = 0x00
    REG_CONFIG = 0x01
    REG_LO_THRESH = 0x02
    REG_HI_THRESH = 0x03

    OS_SINGLE = 0x8000

    MUX_SINGLE_0 = 0x4000
    MUX_SINGLE_1 = 0x5000
    MUX_SINGLE_2 = 0x6000
    MUX_SINGLE_3 = 0x7000

    PGA_6_144V = 0x0000
    PGA_4_096V = 0x0200
    PGA_2_048V = 0x0400
    PGA_1_024V = 0x0600
    PGA_0_512V = 0x0800
    PGA_0_256V = 0x0A00

    MODE_SINGLE = 0x0100

    DR_128SPS = 0x0000
    DR_250SPS = 0x0020
    DR_490SPS = 0x0040
    DR_920SPS = 0x0060

    def __init__(
        self,
        address: int = 0x48,
        scl_pin: int = 5,
        sda_pin: int = 4,
        i2c_id: int = 1,
    ) -> None:
        """Initialize ADS1115.

        Args:
            address: I2C address (0x48-0x4B)
            scl_pin: GPIO pin for SCL
            sda_pin: GPIO pin for SDA
            i2c_id: I2C peripheral (0 or 1)
        """
        self.address = address
        self.scl_pin = scl_pin
        self.sda_pin = sda_pin
        self.i2c_id = i2c_id

        self.i2c = None
        self.gain = self.PGA_4_096V
        self.voltage_multiplier = 0.125
        self._logger = print  # Default to print, can be overridden

    def set_logger(self, logger) -> None:
        """Set custom logger function."""
        self._logger = logger

    def _log(self, message: str) -> None:
        """Log message using configured logger."""
        self._logger("ADS1115", message)

    def init(self) -> bool:
        """Initialize I2C and verify ADS1115 communication."""
        try:
            self.i2c = I2C(
                self.i2c_id,
                scl=Pin(self.scl_pin),
                sda=Pin(self.sda_pin),
                freq=400000,
            )

            devices = self.i2c.scan()
            if self.address not in devices:
                self._log(f"Device not found at 0x{self.address:02X}")
                return False

            self.set_gain(self.PGA_4_096V)
            self._log(f"Initialized at 0x{self.address:02X}")
            return True

        except Exception as e:
            self._log(f"Init failed: {e}")
            return False

    def set_gain(self, gain: int) -> None:
        """Set programmable gain amplifier.

        Args:
            gain: PGA setting (PGA_6_144V, PGA_4_096V, etc.)
        """
        self.gain = gain

        if gain == self.PGA_6_144V:
            self.voltage_multiplier = 0.187500
        elif gain == self.PGA_4_096V:
            self.voltage_multiplier = 0.125000
        elif gain == self.PGA_2_048V:
            self.voltage_multiplier = 0.062500
        elif gain == self.PGA_1_024V:
            self.voltage_multiplier = 0.031250
        elif gain == self.PGA_0_512V:
            self.voltage_multiplier = 0.015625
        elif gain == self.PGA_0_256V:
            self.voltage_multiplier = 0.007813

    def _write_config(self, config: int) -> None:
        """Write configuration register."""
        self.i2c.writeto_mem(
            self.address, self.REG_CONFIG, bytes([(config >> 8) & 0xFF, config & 0xFF])
        )

    def _read_conversion(self) -> int:
        """Read conversion register."""
        data = self.i2c.readfrom_mem(self.address, self.REG_CONVERSION, 2)
        return (data[0] << 8) | data[1]

    def read_voltage(self, channel: int) -> float | None:
        """Read voltage from specified channel.

        Args:
            channel: ADC channel (0-3)

        Returns:
            Voltage in volts, or None on error
        """
        if channel < 0 or channel > 3:
            return None

        try:
            mux = [
                self.MUX_SINGLE_0,
                self.MUX_SINGLE_1,
                self.MUX_SINGLE_2,
                self.MUX_SINGLE_3,
            ][channel]

            config = (
                self.OS_SINGLE | mux | self.gain | self.MODE_SINGLE | self.DR_128SPS
            )

            self._write_config(config)

            time.sleep(0.1)

            raw = self._read_conversion()

            if raw & 0x8000:
                raw = raw - 65536

            voltage = raw * self.voltage_multiplier / 32768.0
            return voltage

        except Exception as e:
            self._log(f"Read error: {e}")
            return None

    def read_raw(self, channel: int) -> int | None:
        """Read raw ADC value from channel.

        Args:
            channel: ADC channel (0-3)

        Returns:
            Raw 16-bit ADC value, or None on error
        """
        if channel < 0 or channel > 3:
            return None

        try:
            mux = [
                self.MUX_SINGLE_0,
                self.MUX_SINGLE_1,
                self.MUX_SINGLE_2,
                self.MUX_SINGLE_3,
            ][channel]

            config = (
                self.OS_SINGLE | mux | self.gain | self.MODE_SINGLE | self.DR_128SPS
            )

            self._write_config(config)
            time.sleep(0.1)

            raw = self._read_conversion()

            if raw & 0x8000:
                raw = raw - 65536

            return raw

        except Exception as e:
            self._log(f"Read error: {e}")
            return None
