"""
Shared Utilities for Pico 2W

Common functions for version management and logging:
    - Version management (read/write/compare)
    - Logging utilities
    - File content copy utility

Logger:
    - set_logger(): Configure logging function
    - log(): Log message with optional tag

Usage:
    from updater_utils import log, set_logger

    set_logger(my_log_function, "TAG")
    log("message")  # Uses default tag
    log("TAG", "message")  # Uses custom tag
"""

VERSION_FILE = "/.version"

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


def log(tag: str, message: str | None = None) -> None:
    """Logger with tag prefix.

    Args:
        tag: Tag/prefix for the message
        message: Message to log (optional for backward compatibility)
    """
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


def copy_file_content(content: str, filename: str) -> bool:
    """Write file content to destination, creating directories if needed."""
    try:
        if "/" in filename:
            dst_dir = filename.rsplit("/", 1)[0]
            try:
                import uos

                uos.mkdir(dst_dir)
            except Exception:
                pass

        with open(filename, "w") as f:
            f.write(content)

        return True
    except Exception as e:
        log(f"Write failed: {filename} -> {e}")
        return False
