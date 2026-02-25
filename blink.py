"""
LED Blink Utilities for Pico 2W
Shared module for LED blink patterns
"""

import machine
import time


# LED Pin - defined once at module level
led = machine.Pin("LED", machine.Pin.OUT)
led.off()


def blink_pattern(pattern: str, delay: float = 0.15, pause: float = 0.3) -> None:
    """Blink LED according to pattern string.

    Args:
        pattern: String of 1s and 0s (e.g., "1010" = on-off-on-off)
        delay: On/off time in seconds
        pause: Pause between blinks in seconds
    """
    for char in pattern:
        if char == "1":
            led.on()
        else:
            led.off()
        time.sleep(delay)
    led.off()
    time.sleep(pause)
