# AGENTS.md - Pico 2W MQTT Client

## ⚡ Quick Start & Commands

### Linting
```bash
pip install ruff
ruff check .              # Check all issues
ruff check . --fix       # Auto-fix
ruff check main.py        # Single file
```

### Deploy to Pico (MicroPico)
**Crucial:** Files must be sent in a specific order to ensure dependencies are present.
```bash
micropico connect
%send main.py app.py config.py secrets.py
%send github_updater.py blink.py wifi_utils.py lte_utils.py updater_utils.py relay_utils.py
%send -r sensors/
```

### Testing/Running
To run the logic in a local Python environment (if mocked):
```python
import main
main.main()
```

---

## 🧠 Architecture & Logic

### Connectivity Strategy
1. **LTE First**: Attempt SIM7600G-H connection (`lte_utils.py`).
2. **WiFi Fallback**: If LTE fails, scan and connect to WiFi (`wifi_utils.py`).
3. **Time Sync**: **CRITICAL.** Pico RTC *must* sync via NTP on boot before MQTT/TLS connections are attempted.

### Key Patterns
- **MQTT Publish-If-**Changed**: Uses `_last_mqtt_values` in `app.py` to only publish when data updates, saving bandwidth.
- **Sensor Manager**: `DS18B20Manager` and `ACS37030` handle hardware retries and periodic sampling.
- **Shared Logger**: Use `log("TAG", "message")` from `updater_utils.py` for consistent formatting.

### Hardware Wiring (SIM7600G-H)
**NOTE: TX/RX MUST BE CROSSED!**
- SIM7600 **TXD** $\rightarrow$ Pico **GP1** (RX)
- SIM7600 **RXD** $\rightarrow$ Pico **GP0** (TX)
- **VIO** $\rightarrow$ **3.3V** (Essential for UART signaling)
- **Power**: SIM7600 requires up to 2A peak; use a separate 5V supply.

---

## 🛠 MicroPython Specifics

- **Time**: Use `time.ticks_ms()` and `time.ticks_diff()` instead of `time.time()`.
- **JSON**: Use `ujson` instead of `json`.
- **Globals**: Declare `global` at the start of functions if modifying module-level state.
- **Constraints**: 
    - Watchdog timer max $\approx$ 8388ms.
    - DS18B20 conversion takes $\approx$ 750ms.
    - Available GPIO: 0-22, 26-28 (23-25, 29 are reserved).

---

## 📂 Files & Convention

- `secrets.py`: **NEVER COMMIT.** Contains WiFi, MQTT, and GitHub credentials.
- `config.py`: All pins and MQTT topics are defined here.
- **Naming**: `snake_case` for functions/vars, `UPPER_SNAKE` for constants, `PascalCase` for classes.
- **Imports**: `stdlib` $\rightarrow$ `third-party` $\rightarrow$ `local`.

