"""
SD Card Updater for Pico 2W

Auto-detects SD card with valid update files at boot and performs
firmware updates without needing a computer.

Update Process:
    1. Check for SD card with update folder
    2. Read version.txt to get new version number
    3. Compare with current version
    4. If newer, backup current firmware
    5. Copy new .py files from SD card
    6. Reboot to apply changes

SD Card Structure:
    /sd/update/
        version.txt    - New version number (e.g., "1.2.0")
        main.py        - Updated main application
        config.py      - Updated configuration
        ...            - Other .py files

Rollback:
    If update fails, automatically restores from backup.
    Manual rollback: Press update button twice within 2 seconds at boot.

Hardware:
    SD card connected via SPI:
    - SCK: GPIO14 (configurable)
    - MOSI: GPIO15 (configurable)
    - MISO: GPIO12 (configurable)
    - CS: GPIO13 (configurable)

Usage:
    1. Create update folder on SD card
    2. Add version.txt with new version
    3. Add updated .py files
    4. Insert SD card into Pico
    5. Reset Pico - update applies automatically

Notes:
    - Only .py files are updated
    - secrets.py is never overwritten
    - Current firmware backed up before update
    - Automatic rollback on failure
"""

import machine
import sdcard
import uos
import time

from blink import blink_pattern
from updater_utils import (
    log,
    read_version,
    write_version,
    compare_versions,
    create_backup,
    restore_backup,
    cleanup_backup,
    copy_file_content,
    detect_rollback_trigger,
    perform_rollback,
)
from config import (
    SD_SCK_PIN,
    SD_MOSI_PIN,
    SD_MISO_PIN,
    SD_CS_PIN,
    UPDATE_BUTTON_PIN,
)

UPDATE_FOLDER = "/sd/update"

sd_card = None
uos_mounted = False


def init_sd() -> bool:
    """Initialize SD card. Returns True on success."""
    global sd_card, uos_mounted

    try:
        spi = machine.SPI(
            0,
            baudrate=100000,
            sck=machine.Pin(SD_SCK_PIN),
            mosi=machine.Pin(SD_MOSI_PIN),
            miso=machine.Pin(SD_MISO_PIN),
            polarity=0,
            phase=0,
        )
        cs = machine.Pin(SD_CS_PIN, machine.Pin.OUT)
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


def apply_update() -> bool:
    """Apply update from SD card. Returns True on success."""
    new_version = read_update_version()
    if not new_version:
        log("No version found on SD")
        blink_pattern("11")
        return False

    current = read_version() or "0.0"
    log(f"Current: {current}, New: {new_version}")

    if new_version <= current:
        log("No update needed")
        blink_pattern("11")
        return False

    files = list_update_files()
    if not files:
        log("No update files found")
        blink_pattern("11")
        return False

    update_files = [f for f in files if f.endswith(".py") or f == "version.txt"]

    log(f"Files to update: {update_files}")

    if not create_backup():
        log("Backup failed, aborting")
        blink_pattern("111")
        return False

    success = True
    for f in update_files:
        if f == "version.txt":
            continue

        try:
            with open(f"{UPDATE_FOLDER}/{f}", "r") as src:
                content = src.read()

            if not copy_file_content(content, f):
                success = False
                break

            log(f"Copied: {f}")
        except Exception as e:
            log(f"Copy failed: {f} -> {e}")
            success = False
            break

    if success:
        write_version(new_version)
        cleanup_backup()
        log(f"Update to {new_version} complete!")
        blink_pattern("11011")
        return True
    else:
        log("Update failed, restoring backup")
        restore_backup()
        cleanup_backup()
        blink_pattern("111")
        return False


def check_and_apply_update() -> bool:
    """Main update check. Returns True if update was applied."""

    if detect_rollback_trigger(UPDATE_BUTTON_PIN):
        log("Rollback triggered!")
        if perform_rollback():
            log("Rebooting...")
            time.sleep(1)
            machine.reset()
        return True

    log("Checking for SD card update...")

    if not init_sd():
        log("No SD card")
        deinit_sd()
        return False

    new_version = read_update_version()
    if not new_version:
        log("No update files on SD")
        deinit_sd()
        return False

    current = read_version() or "0.0"
    if compare_versions(current, new_version) <= 0:
        log(f"No update needed ({current} >= {new_version})")
        deinit_sd()
        return False

    log(f"Update found: {current} -> {new_version}")
    blink_pattern("11")

    success = apply_update()

    deinit_sd()

    if success:
        log("Rebooting...")
        time.sleep(1)
        machine.reset()

    return success
