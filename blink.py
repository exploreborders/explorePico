"""
LED Blink Utilities for Pico 2W
Shared module for LED blink patterns
"""

import machine
import time


def blink(times: int, delay: float = 0.15, pause: float = 0.3) -> None:
    """Blink LED N times.

    Args:
        times: Number of blinks
        delay: On/off time in seconds
        pause: Pause between blinks in seconds
    """
    led = machine.Pin("LED", machine.Pin.OUT)
    for i in range(times):
        led.on()
        time.sleep(delay)
        led.off()
        if i < times - 1:
            time.sleep(pause)


def blink_pattern(pattern: str, delay: float = 0.15, pause: float = 0.3) -> None:
    """Blink LED according to pattern string.

    Args:
        pattern: String of 1s and 0s (e.g., "1010" = on-off-on-off)
        delay: On/off time in seconds
        pause: Pause between blinks in seconds
    """
    led = machine.Pin("LED", machine.Pin.OUT)
    for char in pattern:
        if char == "1":
            led.on()
        else:
            led.off()
        time.sleep(delay)
    led.off()
    time.sleep(pause)
