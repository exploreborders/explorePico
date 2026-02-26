"""
LED Blink Utilities for Pico 2W

Shared module for LED blink patterns to provide visual feedback.
The built-in LED on the Pico is used.

Functions:
    blink_pattern(pattern, delay, pause): Blink LED according to pattern

Pattern Format:
    A string of 1s and 0s where:
    - "1" = LED on
    - "0" = LED off
    Example: "1010" = on-off-on-off

Default Timings:
    - delay: 0.15s per blink
    - pause: 0.3s after pattern completes

Common Patterns:
    "10"      - Quick blink (connecting)
    "1010"    - Double blink (connected)
    "11011"   - Triple blink (ready)
    "111"     - Error pattern

Usage:
    from blink import blink_pattern, led

    # Blink connection pattern
    blink_pattern("1010")

    # Control LED directly
    led.on()
    led.off()

Hardware:
    Uses built-in LED on GPIO "LED" (Pico W: WLED)
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
