"""
SD Card Code Updater for Pico 2W
Triggers update via button press, with backup/rollback support
"""

import machine
import sdcard
import uos
import time

SD_SCK = 14
SD_MOSI = 15
SD_MISO = 12
SD_CS = 13
UPDATE_BUTTON = 10

VERSION_FILE = "/.version"
UPDATE_FOLDER = "/sd/update"

sd_card = None
uos_mounted = False


def log(msg: str) -> None:
    """Simple logger."""
    print(f"[SDUPD] {msg}")


def blink_led(pattern: str, delay: float = 0.15) -> None:
    """Blink LED for feedback."""
    led = machine.Pin("LED", machine.Pin.OUT)
    for char in pattern:
        led.value(1 if char == "1" else 0)
        time.sleep(delay)
    led.value(0)


def init_sd() -> bool:
    """Initialize SD card. Returns True on success."""
    global sd_card, uos_mounted

    try:
        spi = machine.SPI(
            0,
            baudrate=400000,
            sck=machine.Pin(SD_SCK),
            mosi=machine.Pin(SD_MOSI),
            miso=machine.Pin(SD_MISO),
        )
        cs = machine.Pin(SD_CS, machine.Pin.OUT)
        sd_card = sdcard.SDCard(spi, cs)
        uos.mount(sd_card, "/sd")
        uos_mounted = True
        log("SD card mounted")
        return True
    except Exception as e:
        log(f"SD init failed: {e}")
        return False


def deinit_sd() -> None:
    """Unmount SD card."""
    global uos_mounted
    if uos_mounted:
        try:
            uos.umount("/sd")
        except Exception:
            pass
        uos_mounted = False


def read_version() -> str | None:
    """Read current version from internal flash."""
    try:
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    except Exception:
        return None


def write_version(version: str) -> None:
    """Write version to internal flash."""
    with open(VERSION_FILE, "w") as f:
        f.write(version)


def check_update_trigger() -> bool:
    """Check if update button is pressed at boot."""
    btn = machine.Pin(UPDATE_BUTTON, machine.Pin.IN, machine.Pin.PULL_UP)
    return not btn.value()


def detect_rollback_trigger() -> bool:
    """Check for double-button press within 2 seconds at boot."""
    btn = machine.Pin(UPDATE_BUTTON, machine.Pin.IN, machine.Pin.PULL_UP)

    if btn.value() == 0:
        time.sleep(0.1)
        first_press_time = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), first_press_time) < 2000:
            if btn.value() == 1:
                time.sleep(0.1)
                second_wait_start = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), second_wait_start) < 1000:
                    if btn.value() == 0:
                        time.sleep(0.1)
                        while btn.value() == 0:
                            pass
                        return True
                break
        while btn.value() == 0:
            pass

    return False


def perform_rollback() -> bool:
    """Restore from backup. Returns True on success."""
    log("Rolling back...")
    blink_led("010")

    try:
        files = uos.listdir("/backup")
        if not files:
            log("No backup found")
            blink_led("1")
            return False

        for f in files:
            try:
                with open(f"/backup/{f}", "r") as src:
                    content = src.read()
                with open(f, "w") as dst:
                    dst.write(content)
            except Exception:
                pass

        try:
            uos.remove(VERSION_FILE)
        except Exception:
            pass

        cleanup_backup()

        log("Rollback complete")
        blink_led("1010")
        return True

    except Exception as e:
        log(f"Rollback failed: {e}")
        blink_led("000")
        return False


def list_update_files() -> list[str] | None:
    """List files in update folder. Returns None if folder doesn't exist."""
    try:
        files = uos.listdir(UPDATE_FOLDER)
        return [f for f in files if not f.startswith(".")]
    except Exception:
        return None


def read_update_version() -> str | None:
    """Read version from SD card update folder."""
    try:
        with open(f"{UPDATE_FOLDER}/version.txt", "r") as f:
            return f.read().strip()
    except Exception:
        return None


def copy_file(src: str, dst: str) -> bool:
    """Copy file from SD to internal flash. Returns True on success."""
    try:
        if "/" in dst:
            dst_dir = dst.rsplit("/", 1)[0]
            try:
                uos.mkdir(dst_dir)
            except Exception:
                pass

        with open(f"{UPDATE_FOLDER}/{src}", "r") as f:
            content = f.read()

        with open(dst, "w") as f:
            f.write(content)

        log(f"Copied: {src} -> {dst}")
        return True
    except Exception as e:
        log(f"Copy failed: {src} -> {e}")
        return False


def create_backup() -> bool:
    """Backup current files before update. Returns True on success."""
    try:
        try:
            uos.rmdir("/backup")
        except Exception:
            pass

        uos.mkdir("/backup")

        files_to_backup = ["main.py", "config.py", "secrets.py"]
        for f in files_to_backup:
            try:
                with open(f, "r") as src:
                    content = src.read()
                with open(f"/backup/{f}", "w") as dst:
                    dst.write(content)
            except Exception:
                pass

        try:
            uos.mkdir("/backup/sensors")
            sensor_files = uos.listdir("sensors")
            for sf in sensor_files:
                if sf.endswith(".py"):
                    with open(f"sensors/{sf}", "r") as src:
                        content = src.read()
                    with open(f"/backup/sensors/{sf}", "w") as dst:
                        dst.write(content)
        except Exception:
            pass

        log("Backup created")
        return True
    except Exception as e:
        log(f"Backup failed: {e}")
        return False


def restore_backup() -> bool:
    """Restore files from backup. Returns True on success."""
    try:
        files = uos.listdir("/backup")
        for f in files:
            try:
                if f == "sensors":
                    sensor_files = uos.listdir("/backup/sensors")
                    try:
                        uos.mkdir("sensors")
                    except Exception:
                        pass
                    for sf in sensor_files:
                        with open(f"/backup/sensors/{sf}", "r") as src:
                            content = src.read()
                        with open(f"sensors/{sf}", "w") as dst:
                            dst.write(content)
                else:
                    with open(f"/backup/{f}", "r") as src:
                        content = src.read()
                    with open(f, "w") as dst:
                        dst.write(content)
            except Exception:
                pass

        uos.rmdir("/backup")

        log("Backup restored")
        return True
    except Exception as e:
        log(f"Restore failed: {e}")
        return False


def cleanup_backup() -> None:
    """Remove backup folder."""
    try:
        files = uos.listdir("/backup")
        for f in files:
            if f == "sensors":
                try:
                    sensor_files = uos.listdir("/backup/sensors")
                    for sf in sensor_files:
                        try:
                            uos.remove(f"/backup/sensors/{sf}")
                        except Exception:
                            pass
                    uos.rmdir("/backup/sensors")
                except Exception:
                    pass
            else:
                try:
                    uos.remove(f"/backup/{f}")
                except Exception:
                    pass
        uos.rmdir("/backup")
    except Exception:
        pass


def apply_update() -> bool:
    """Apply update from SD card. Returns True on success."""
    blink_led("11")

    new_version = read_update_version()
    if not new_version:
        log("No version found on SD")
        blink_led("10")
        return False

    current = read_version() or "0.0"
    log(f"Current: {current}, New: {new_version}")

    if new_version <= current:
        log("No update needed")
        blink_led("10")
        return False

    files = list_update_files()
    if not files:
        log("No update files found")
        blink_led("10")
        return False

    update_files = [f for f in files if f.endswith(".py") or f == "version.txt"]

    log(f"Files to update: {update_files}")

    if not create_backup():
        log("Backup failed, aborting")
        blink_led("000")
        return False

    success = True
    for f in update_files:
        if f == "version.txt":
            continue

        if f == "main.py":
            dst = "main.py"
        elif f == "config.py":
            dst = "config.py"
        elif f == "secrets.py":
            dst = "secrets.py"
        elif f.startswith("sensors/"):
            dst = f
        else:
            dst = f

        if not copy_file(f, dst):
            success = False
            break

    if success:
        write_version(new_version)
        cleanup_backup()
        log(f"Update to {new_version} complete!")
        blink_led("111")
        return True
    else:
        log("Update failed, restoring backup")
        restore_backup()
        cleanup_backup()
        blink_led("000")
        return False


def check_and_apply_update() -> bool:
    """Main update check. Returns True if update was applied."""

    if detect_rollback_trigger():
        log("Rollback triggered!")
        if perform_rollback():
            log("Rebooting...")
            time.sleep(1)
            machine.reset()
        return True

    if not check_update_trigger():
        return False

    log("Update button pressed!")
    blink_led("1")

    if not init_sd():
        blink_led("000")
        deinit_sd()
        return False

    success = apply_update()

    deinit_sd()

    if success:
        log("Rebooting...")
        time.sleep(1)
        machine.reset()

    return success
