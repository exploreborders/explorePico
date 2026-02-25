"""
Shared Updater Utilities for Pico 2W
Common functions for SD Card and GitHub updaters
"""

import machine
import time
import uos

VERSION_FILE = "/.version"
BACKUP_FOLDER = "/backup"

# Files to exclude from backup
EXCLUDE_FILES = {".version", "secrets.py"}

# Default logger - can be overridden
_log_fn = None
_log_tag = "UPD"


def set_logger(log_fn, tag: str = "UPD") -> None:
    """Set the logger function to use.

    Args:
        log_fn: Function that takes (tag, message) arguments
        tag: Default tag to use (default: "UPD")
    """
    global _log_fn, _log_tag
    _log_fn = log_fn
    _log_tag = tag


def log(tag: str, message: str = None) -> None:
    """Logger with tag prefix.

    Args:
        tag: Tag/prefix for the message
        message: Message to log (optional for backward compatibility)
    """
    # Handle backward compatibility: if only one arg, treat as message
    if message is None:
        message = tag
        tag = _log_tag

    full_msg = f"[{tag}] {message}"

    if _log_fn:
        _log_fn(tag, message)
    else:
        print(full_msg)


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


def parse_version(version: str) -> tuple:
    """Parse version string to tuple for comparison.

    Handles formats like:
    - "1.7" -> (1, 7, 0)
    - "1.7.0" -> (1, 7, 0)
    - "v1.7" -> (1, 7, 0)
    - "1" -> (1, 0, 0)
    """
    try:
        version = version.replace("v", "").strip()
        parts = version.split(".")

        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0

        return (major, minor, patch)
    except Exception:
        return (0, 0, 0)


def compare_versions(current: str, new: str) -> int:
    """Compare versions. Returns 1 if new > current, 0 if equal, -1 if older."""
    current_tuple = parse_version(current)
    new_tuple = parse_version(new)

    if new_tuple > current_tuple:
        return 1
    elif new_tuple == current_tuple:
        return 0
    else:
        return -1


def list_python_files(root_dir: str = ".") -> list[tuple[str, str]]:
    """Recursively list all .py files in directory.

    Returns list of (source_path, dest_relative_path) tuples.
    Excludes files in EXCLUDE_FILES and __pycache__.
    """
    files = []

    def scan_dir(current_dir: str):
        try:
            entries = uos.listdir(current_dir)
        except Exception:
            return

        for entry in entries:
            # Skip hidden files and pycache
            if entry.startswith("."):
                continue
            if entry == "__pycache__":
                continue

            full_path = f"{current_dir}/{entry}" if current_dir != "." else entry

            try:
                stat = uos.stat(full_path)
                if stat[0] & 0x4000:  # Directory
                    # Only recurse into known subdirectories
                    if entry in ("sensors",):
                        scan_dir(full_path)
                elif entry.endswith(".py") and entry not in EXCLUDE_FILES:
                    # Store as relative path from root
                    files.append((full_path, full_path))
            except Exception:
                pass

    scan_dir(root_dir)
    return files


def create_backup() -> bool:
    """Backup all Python files before update."""
    try:
        # Remove existing backup if any
        try:
            uos.rmdir(BACKUP_FOLDER)
        except Exception:
            pass

        uos.mkdir(BACKUP_FOLDER)

        # Get all .py files
        files_to_backup = list_python_files(".")

        # Backup each file
        for src_path, dst_rel_path in files_to_backup:
            try:
                with open(src_path, "r") as src:
                    content = src.read()
                dst_path = f"{BACKUP_FOLDER}/{dst_rel_path}"

                # Create subdirectory if needed
                if "/" in dst_rel_path:
                    dst_dir = dst_rel_path.rsplit("/", 1)[0]
                    try:
                        uos.mkdir(f"{BACKUP_FOLDER}/{dst_dir}")
                    except Exception:
                        pass

                with open(dst_path, "w") as dst:
                    dst.write(content)
            except Exception as e:
                log(f"Backup error: {src_path} -> {e}")

        log(f"Backup created ({len(files_to_backup)} files)")
        return True
    except Exception as e:
        log(f"Backup failed: {e}")
        return False


def restore_backup() -> bool:
    """Restore all files from backup."""
    try:
        files = uos.listdir(BACKUP_FOLDER)

        for f in files:
            src_path = f"{BACKUP_FOLDER}/{f}"

            try:
                stat = uos.stat(src_path)
                if stat[0] & 0x4000:  # Directory
                    # Create directory in root
                    try:
                        uos.mkdir(f)
                    except Exception:
                        pass

                    # Restore all files in directory
                    subfiles = uos.listdir(src_path)
                    for sf in subfiles:
                        with open(f"{src_path}/{sf}", "r") as src:
                            content = src.read()
                        with open(f"{f}/{sf}", "w") as dst:
                            dst.write(content)
                else:
                    # Regular file
                    with open(src_path, "r") as src:
                        content = src.read()
                    with open(f, "w") as dst:
                        dst.write(content)
            except Exception as e:
                log(f"Restore error: {f} -> {e}")

        uos.rmdir(BACKUP_FOLDER)
        log("Backup restored")
        return True
    except Exception as e:
        log(f"Restore failed: {e}")
        return False


def cleanup_backup() -> None:
    """Remove backup folder."""
    try:
        files = uos.listdir(BACKUP_FOLDER)
        for f in files:
            path = f"{BACKUP_FOLDER}/{f}"
            try:
                stat = uos.stat(path)
                if stat[0] & 0x4000:  # Directory
                    subfiles = uos.listdir(path)
                    for sf in subfiles:
                        uos.remove(f"{path}/{sf}")
                    uos.rmdir(path)
                else:
                    uos.remove(path)
            except Exception:
                pass
        uos.rmdir(BACKUP_FOLDER)
    except Exception:
        pass


def copy_file_content(content: str, filename: str) -> bool:
    """Write file content to destination, creating directories if needed."""
    try:
        if "/" in filename:
            dst_dir = filename.rsplit("/", 1)[0]
            try:
                uos.mkdir(dst_dir)
            except Exception:
                pass

        with open(filename, "w") as f:
            f.write(content)

        return True
    except Exception as e:
        log(f"Write failed: {filename} -> {e}")
        return False


def detect_rollback_trigger(button_pin: int = 10) -> bool:
    """Check for double-button press within 2 seconds at boot.

    Args:
        button_pin: GPIO pin for the button (default: 10)

    Returns:
        True if rollback is triggered
    """
    btn = machine.Pin(button_pin, machine.Pin.IN, machine.Pin.PULL_UP)

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
    from blink import blink_pattern

    log("Rolling back...")
    blink_pattern("010")

    try:
        files = uos.listdir(BACKUP_FOLDER)
        if not files:
            log("No backup found")
            blink_pattern("1")
            return False

        if not restore_backup():
            blink_pattern("000")
            return False

        try:
            uos.remove(VERSION_FILE)
        except Exception:
            pass

        cleanup_backup()

        log("Rollback complete")
        blink_pattern("1010")
        return True

    except Exception as e:
        log(f"Rollback failed: {e}")
        blink_pattern("000")
        return False
