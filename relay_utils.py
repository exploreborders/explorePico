from machine import Pin


class RelayManager:
    def __init__(self, pins: list):
        self._pins: list = []
        self._states: dict = {}
        self._logger = None

        for i, pin_num in enumerate(pins):
            pin = Pin(pin_num, Pin.OUT)
            pin.value(0)  # Start OFF (LOW for active HIGH module)
            self._pins.append(pin)
            self._states[i] = False

    def set_logger(self, logger_fn) -> None:
        self._logger = logger_fn

    def _log(self, tag: str, message: str) -> None:
        if self._logger:
            self._logger(tag, message)

    def set_relay(self, index: int, state: bool) -> None:
        if index < 0 or index >= len(self._pins):
            self._log("RELAY", f"Invalid index: {index}")
            return

        self._pins[index].value(1 if state else 0)
        self._states[index] = state
        self._log("RELAY", f"Relay {index + 1}: {'ON' if state else 'OFF'}")

    def get_relay(self, index: int) -> bool:
        if index < 0 or index >= len(self._pins):
            return False
        return self._states.get(index, False)

    def get_all_states(self) -> list:
        return [self._states.get(i, False) for i in range(len(self._pins))]

    def all_off(self) -> None:
        for i in range(len(self._pins)):
            self.set_relay(i, False)
        self._log("RELAY", "All relays OFF")
