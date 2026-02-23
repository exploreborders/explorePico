# Pico 2W Car MQTT Project - Implementation Plan

## Project Overview

MicroPython project for Raspberry Pi Pico 2W with cellular connectivity (SIM7600G-H), integrating with Home Assistant via MQTT. Monitors vehicle systems and controls relays.

**Dual Connectivity:** Primary cellular (SIM7600) with WiFi fallback when cellular unavailable.

## Hardware Configuration

### Pin Assignment

| Component | Pins | Interface | Notes |
|-----------|------|-----------|-------|
| SIM7600G-H | GP0 (TX), GP1 (RX) | UART0 | 115200 baud, power-on via GP20 |
| DS18B20 | GP22 | 1-Wire | 2 sensors: water temp, fridge area temp |
| Water Level | GP26 (ADC0) | ADC | Voltage divider: 10kΩ + 0-190Ω sensor |
| ACS37030 #1 | GP27 (ADC1) | ADC | Fridge current (±20A, 3.3V) |
| ACS37030 #2 | GP28 (ADC2) | ADC | Fan current (±20A, 3.3V) |
| ACS37030 #3 | GP29 (ADC3) | ADC | Inverter current (±20A, 3.3V) |
| Relay #1 | GP6 | GPIO | Fridge control |
| Relay #2 | GP7 | GPIO | Fan control |
| Relay #3 | GP8 | GPIO | Inverter control |
| Relay #4 | GP9 | GPIO | Spare |
| LED | GP25 | GPIO | Status LED (built-in) |

### Sensors

| Sensor | Model | Quantity | Range | Interface |
|--------|-------|----------|-------|-----------|
| Temperature | DS18B20 waterproof | 2 | -55°C to +125°C | 1-Wire |
| Current | ACS37030LLZATR-020B3 | 3-4 | ±20A | ADC (3.3V native) |
| Water Level | Resistive (0-190Ω) | 1 | 0-100% | ADC |
| GPS | SIM7600G-H | 1 | - | UART |

### ACS37030LLZATR-020B3 Specifications

| Parameter | Value |
|-----------|-------|
| Supply Voltage | 3.0V - 3.6V (3.3V nominal) |
| Current Range | ±20A (bidirectional) |
| Sensitivity | 66 mV/A |
| Zero Point | 1.65V (Vcc/2) |
| Response Time | 40 ns |
| Accuracy | ±2% sensitivity error |
| Operating Temp | -40°C to 150°C |
| Isolation | Galvanic |

### ADC Calculation (ACS37030)

```
ADC reading (0-4095) → Voltage → Current

Voltage = (adc_value / 4095) * 3.3
Current = (Voltage - 1.65) / 0.066  # 66 mV/A sensitivity

Example:
- 0A: ADC = 2048, Voltage = 1.65V
- 10A: ADC ~ 2500, Voltage ~ 2.31V
- -10A: ADC ~ 1596, Voltage ~ 0.99V
```

## Dual Connectivity Architecture

### Overview

| Connection | When Used | Broker | HA Available? |
|------------|-----------|--------|---------------|
| **Cellular** (primary) | Normal operation | explorehome.duckdns.org | ✅ Yes |
| **WiFi** (fallback) | No cellular | iPhone local broker (Fast MQTT Broker Mobile) | ❌ No - local only |

### Connection Logic

```
1. Start: Try cellular first (SIM7600)
2. If cellular fails → switch to WiFi (phone hotspot)
3. Periodic check (every 5 min): try cellular again
4. If cellular returns → switch back to cellular
```

### MQTT Client IDs
- `pico_cellular` - when on cellular
- `pico_wifi` - when on WiFi fallback

### State Re-Publish on Connection Change

When switching between cellular and WiFi:
1. Connect to new broker
2. Re-publish ALL discovery configs (retain = True)
3. Re-publish ALL current sensor states (retain = True)
4. Subscribe to control topics

This ensures new broker has all retained messages and current values.

### WiFi Fallback Details

**Use case:** When no mobile internet available
- Pico connects to iPhone WiFi hotspot
- iPhone runs "Fast MQTT Broker Mobile" app ($5.99)
- Local broker port: 1883 (same as home broker)
- Control via MQTT client app on iPhone (MQTTAnalyzer, EasyMQTT, etc.)

**Note:** Home Assistant NOT accessible during WiFi fallback - local control only.

### Secrets Configuration

```python
# Cellular (primary)
CELLULAR_APN = "o2.de"
MQTT_BROKER = "explorehome.duckdns.org"
MQTT_PORT = 1883
MQTT_USER = "your_mqtt_user"
MQTT_PASSWORD = "your_mqtt_password"

# WiFi Fallback (iPhone hotspot)
WIFI_SSID = "YourPhoneHotspot"
WIFI_PASSWORD = "hotspotpassword"
WIFI_MQTT_BROKER = "iPhone_IP_address"  # e.g., "172.20.10.1"
WIFI_MQTT_PORT = 1883
```

## MQTT Configuration

### Topics Structure

#### Discovery Topics (Home Assistant)

```
homeassistant/sensor/pico/temp_water/config
homeassistant/sensor/pico/temp_fridge_area/config
homeassistant/sensor/pico/current_fridge/config
homeassistant/sensor/pico/current_fan/config
homeassistant/sensor/pico/current_inverter/config
homeassistant/sensor/pico/water_level/config
homeassistant/sensor/pico/gps_latitude/config
homeassistant/sensor/pico/gps_longitude/config
homeassistant/sensor/pico/gps_speed/config
homeassistant/sensor/pico/gps_altitude/config
homeassistant/sensor/pico/internal_temp/config
homeassistant/switch/pico/fridge/config
homeassistant/switch/pico/fan/config
homeassistant/switch/pico/inverter/config
```

#### State Topics

```
pico/sensor/temp_water/state
pico/sensor/temp_fridge_area/state
pico/sensor/current_fridge/state
pico/sensor/current_fan/state
pico/sensor/current_inverter/state
pico/sensor/water_level/state
pico/sensor/gps/latitude
pico/sensor/gps/longitude
pico/sensor/gps/speed
pico/sensor/gps/altitude
pico/sensor/internal_temp/state
```

#### Control Topics

```
pico/switch/fridge/set
pico/switch/fridge/state
pico/switch/fan/set
pico/switch/fan/state
pico/switch/inverter/set
pico/switch/inverter/state
```

### Discovery Payloads

#### Temperature Sensor Example

```json
{
  "name": "Pico Water Temperature",
  "unique_id": "pico_water_temp",
  "device_class": "temperature",
  "unit_of_measurement": "°C",
  "state_topic": "pico/sensor/temp_water/state",
  "availability_topic": "pico/status",
  "payload_available": "online",
  "payload_not_available": "offline"
}
```

#### Current Sensor Example

```json
{
  "name": "Pico Fridge Current",
  "unique_id": "pico_current_fridge",
  "device_class": "current",
  "unit_of_measurement": "A",
  "state_topic": "pico/sensor/current_fridge/state",
  "availability_topic": "pico/status",
  "payload_available": "online",
  "payload_not_available": "offline"
}
```

#### Switch Example

```json
{
  "name": "Pico Fridge",
  "unique_id": "pico_fridge",
  "command_topic": "pico/switch/fridge/set",
  "state_topic": "pico/switch/fridge/state",
  "availability_topic": "pico/status",
  "payload_available": "online",
  "payload_not_available": "offline",
  "payload_on": "ON",
  "payload_off": "OFF"
}
```

## Auto Control Logic

### Fan Control (Hysteresis)

```python
FAN_ON_TEMP = 30  # °C
FAN_OFF_TEMP = 25  # °C

def update_fan():
    global fan_state
    if fridge_area_temp > FAN_ON_TEMP and not fan_state:
        relay_on(FAN_RELAY)
        fan_state = True
    elif fridge_area_temp < FAN_OFF_TEMP and fan_state:
        relay_off(FAN_RELAY)
        fan_state = False
```

### Relay States

| Relay | Default | Control | Auto/Manual |
|-------|---------|---------|-------------|
| Fridge | OFF | Manual (HA) | Manual |
| Fan | OFF | Auto + Manual | Auto (temp-based) |
| Inverter | OFF | Manual (HA) | Manual |
| Spare | OFF | Manual (HA) | Manual |

## SIM7600G-H Integration

### AT Command Sequence

```python
# Initialize
AT
AT+CPIN?
AT+CREG?

# GPRS
AT+CGDCONT=1,"IP","o2.de"
AT+CGACT=1,1

# MQTT
AT+CMQTTSTART
AT+CMQTTACCQ=0,"pico_xxx"
AT+CMQTTCONNECT=0,"mqtt.server.com",1883,60
AT+CMQTTPUB=0,"topic",0,0,"payload"
```

### GPS NMEA Parsing

```python
# $GNGGA sentence
# $GNGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,47.0,M,,*47

latitude = parse_nmea_degrees("4807.038")  # 48.1173°
longitude = parse_nmea_degrees("01131.000")  # 11.5167°
altitude = 545.4  # meters
```

## File Structure

```
secondTest/
├── plan.md                    # This file
├── main.py                    # Main application
├── config.py                  # Configuration
├── secrets.py                 # Credentials (not committed)
├── AGENTS.md                  # Agent instructions
├── README.md                  # Project docs
├── .gitignore
└── sensors/
    ├── __init__.py
    ├── ds18b20.py            # DS18B20 driver
    ├── acs37030.py           # NEW - ACS37030 driver
    ├── water_level.py        # NEW - Water level sensor
    └── gps.py                # NEW - GPS parsing

modem/                        # NEW
├── __init__.py
└── sim7600.py                # SIM7600 driver
```

## Implementation Phases

### Phase 1: Core Infrastructure
- [x] Set up project structure
- [x] Create config.py with pin definitions
- [x] Create secrets.py template
- [x] Set up logging system

### Phase 2: SIM7600 Integration
- [ ] Create modem/sim7600.py driver
- [ ] Implement AT command handling
- [ ] Implement MQTT over AT commands
- [ ] Test cellular connectivity
- [ ] Use cellular as primary connection

### Phase 3: GPS
- [ ] Implement NMEA parsing
- [ ] Add GPS reading to main loop
- [ ] Publish GPS data to MQTT

### Phase 4: Temperature Sensors
- [ ] Integrate existing DS18B20 code
- [ ] Map sensors: index 0 = water, index 1 = fridge area
- [ ] Test both sensors

### Phase 5: Current Sensors
- [ ] Create sensors/acs37030.py driver
- [ ] Implement ADC reading and conversion
- [ ] Add 3 current sensors to main loop

### Phase 6: Water Level
- [ ] Create sensors/water_level.py driver
- [ ] Implement voltage divider calculation
- [ ] Map to percentage (0-190Ω → 0-100%)

### Phase 7: Relay Control
- [ ] Add relay GPIO setup
- [ ] Implement MQTT subscribe for control
- [ ] Add relay state tracking

### Phase 8: Auto Logic
- [ ] Implement fan hysteresis control
- [ ] Add temperature-based automation
- [ ] Test manual override

### Phase 9: Home Assistant Integration
- [ ] Implement discovery messages
- [ ] Add availability tracking
- [ ] Test all sensors and switches in HA

### Phase 10: WiFi Fallback (Dual Connectivity)
- [ ] Add WiFi credentials to config.py and secrets.py
- [ ] Implement WiFi connection function
- [ ] Implement cellular-first, WiFi-fallback logic
- [ ] Add periodic cellular check (every 5 min)
- [ ] Implement state re-publish on connection switch
- [ ] Track connection type (cellular/wifi)
- [ ] Use different client IDs per connection

### Phase 11: Testing & Optimization
- [ ] Full system test
- [ ] Connection reliability testing
- [ ] Power consumption optimization

## Testing Checklist

- [x] WiFi connects to home network
- [x] MQTT connection established to home broker
- [ ] SIM7600 connects to cellular network
- [ ] Cellular MQTT connection established
- [ ] All sensors read correctly
- [ ] GPS returns valid coordinates
- [ ] Relays respond to MQTT commands
- [ ] Fan auto-control works
- [ ] HA discovers all entities
- [ ] System handles reconnection
- [ ] WiFi fallback activates when cellular fails
- [ ] Connection switches back to cellular when available
- [ ] States re-published on connection change
- [ ] Local iPhone broker works for WiFi fallback

## Notes

### O2 APN (Germany)
- APN: `o2.de`
- Username: (empty)
- Password: (empty)

### iPhone Local MQTT Broker
- App: **Fast MQTT Broker Mobile** ($5.99)
- App Store: https://apps.apple.com/us/app/fast-mqtt-broker-mobile/id6751751797
- Port: 1883 (default)
- Use same credentials as home broker
- Control via MQTT client app (MQTTAnalyzer, EasyMQTT)

### Water Level Sensor
- Empty: ~190Ω
- Full: ~0Ω
- Formula: `percentage = (190 - resistance) / 190 * 100`

### Power Considerations
- SIM7600: ~500mA peak, ~50mA standby
- Pico 2W: ~40-150mA depending on load
- ACS37030: ~25mA per sensor
- Total estimate: 600-800mA peak

### Memory Constraints
- MicroPython heap: ~40KB
- Keep code minimal
- No large buffers

## Future Enhancements

- SD card data logging
- OTA firmware updates
- SMS alerts
- Battery voltage monitoring
- Additional sensors (door, motion)
