from updater_utils import log


class MMA845X:
    """Low-level driver for MMA845X accelerometer."""

    # Register Map
    REG_X_MSB = 0x01
    REG_CTRL_REG1 = 0x2A

    def __init__(self, i2c, address=0x1D):
        self.i2c = i2c
        self.address = address

    def setup(self):
        """Initialize sensor to active mode."""
        try:
            import time

            # Put in standby mode first
            self.i2c.writeto(self.address, bytes([self.REG_CTRL_REG1, 0x00]))
            time.sleep_ms(10)

            # Set active mode (bit 0 = 1)
            self.i2c.writeto(self.address, bytes([self.REG_CTRL_REG1, 0x01]))
            time.sleep_ms(10)

            return True
        except Exception as e:
            log("MMA845X", f"Setup failed: {e}")
            return False

    def read_axes(self):
        """Read X, Y, Z axes as floats."""
        try:
            # Read 6 bytes starting from X_MSB
            data = self.i2c.readfrom_mem(self.address, self.REG_X_MSB, 6)

            def to_signed(msb, lsb):
                val = (msb << 8) | lsb
                # Right shift by 4 (12-bit resolution)
                val >>= 4
                if val & 0x800:
                    val -= 0x1000
                return val

            # For ±2g range: 1024 counts per g
            x = to_signed(data[0], data[1]) / 1024.0
            y = to_signed(data[2], data[3]) / 1024.0
            z = to_signed(data[4], data[5]) / 1024.0
            return x, y, z
        except Exception as e:
            log("MMA845X", f"Read error: {e}")
            return None


class MMA845XManager:
    """High-level manager for MMA845X using the project's pattern."""

    def __init__(self, i2c, address, logger_func):
        self.i2c = i2c
        self.address = address
        self.log = logger_func
        self.driver = MMA845X(i2c, address)
        self.initialized = False

    def initialize(self):
        """Initialize the hardware."""
        if self.driver.setup():
            self.initialized = True
            self.log("MMA845X", "Initialized successfully")
            return True
        return False

    def read(self):
        """Perform a sensor reading."""
        if not self.initialized:
            if not self.initialize():
                return None

        axes = self.driver.read_axes()
        if axes is None:
            return None
        return {"x": axes[0], "y": axes[1], "z": axes[2]}
