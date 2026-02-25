"""
GitHub WiFi Updater for Pico 2W
Checks GitHub releases for updates and auto-updates
Downloads all .py files from release assets
"""

import machine
import time
import ujson

try:
    import urequests as requests
except ImportError:
    try:
        import requests
    except ImportError:
        requests = None

from blink import blink_pattern
from wifi_utils import is_connected
from updater_utils import (
    log,
    read_version,
    write_version,
    compare_versions,
    create_backup,
    restore_backup,
    cleanup_backup,
    copy_file_content,
)


def get_latest_release(owner: str, repo: str) -> dict | None:
    """Fetch latest release info from GitHub API."""
    if requests is None:
        log("urequests not available")
        return None

    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = ujson.loads(response.text)
            return {
                "tag": data.get("tag_name", "").lstrip("v"),
                "name": data.get("name", ""),
                "assets": data.get("assets", []),
            }
        else:
            log(f"GitHub API error: {response.status_code}")
            return None
    except Exception as e:
        log(f"Request failed: {e}")
        return None


def download_and_update(owner: str, repo: str, release_info: dict) -> bool:
    """Download files from GitHub release and update."""
    log("Downloading files...")
    blink_pattern("11")

    if not create_backup():
        blink_pattern("000")
        return False

    files_updated = 0
    files_failed = False

    assets = release_info.get("assets", [])

    for asset in assets:
        filename = asset.get("name", "")
        url = asset.get("browser_download_url", "")

        if not filename or not url:
            continue

        if not filename.endswith(".py"):
            continue

        try:
            log(f"Downloading {filename}...")
            response = requests.get(url, timeout=30)

            if response.status_code != 200:
                log(f"Download failed ({response.status_code}): {filename}")
                files_failed = True
                break

            content = response.text

            if not copy_file_content(content, filename):
                files_failed = True
                break

            log(f"Updated: {filename}")
            files_updated += 1

        except Exception as e:
            log(f"Failed to update {filename}: {e}")
            files_failed = True
            break

    if files_failed:
        log("Update failed, restoring backup")
        restore_backup()
        cleanup_backup()
        blink_pattern("000")
        return False

    cleanup_backup()
    log(f"Updated {files_updated} files")
    blink_pattern("111")
    return True


def check_and_update(owner: str, repo: str) -> bool:
    """Check for updates from GitHub and apply if available."""
    if not is_connected():
        log("WiFi not connected")
        return False

    log("Checking GitHub for updates...")
    blink_pattern("1")

    release = get_latest_release(owner, repo)
    if not release:
        log("No release found or API error")
        return False

    new_version = release.get("tag", "")
    if not new_version:
        log("No version in release")
        return False

    current = read_version() or "0.0"

    log(f"Current: {current}, Latest: {new_version}")

    result = compare_versions(current, new_version)

    if result <= 0:
        log("No update needed")
        return False

    log(f"Update available: {new_version}")

    if download_and_update(owner, repo, release):
        write_version(new_version)
        log(f"Updated to {new_version}, rebooting...")
        time.sleep(1)
        machine.reset()
        return True

    return False


def check_for_update(owner: str, repo: str) -> bool:
    """Check if update is available without applying."""
    if not is_connected():
        return False

    release = get_latest_release(owner, repo)
    if not release:
        return False

    new_version = release.get("tag", "")
    if not new_version:
        return False

    current = read_version() or "0.0"

    return compare_versions(current, new_version) > 0
