"""
GitHub WiFi Updater for Pico 2W

Checks GitHub releases for updates and automatically downloads
and applies firmware updates over WiFi.

Update Process:
    1. Connect to WiFi
    2. Fetch latest release from GitHub API
    3. Compare version with current
    4. If newer, backup current firmware
    5. Download .py files from release assets
    6. Reboot to apply changes

GitHub Setup:
    1. Create a GitHub repository with .py files
    2. Create a release with version tag (e.g., v1.2.0)
    3. Upload .py files as release assets
    4. Configure GITHUB_OWNER and GITHUB_REPO in config.py

Release Asset Naming:
    Files must be named with .py extension:
    - main.py
    - config.py
    - sensors/ds18b20.py
    - etc.

Rollback:
    If update fails, automatically restores from backup.
    Manual rollback: Press update button twice within 2 seconds at boot.

Usage:
    Automatic on boot if WiFi is available.
    Configure GITHUB_OWNER and GITHUB_REPO in config.py.

API:
    Uses GitHub REST API: https://api.github.com/repos/{owner}/{repo}/releases/latest

Notes:
    - Requires urequests library
    - Only .py files are downloaded
    - secrets.py is never overwritten
    - Automatic rollback on failure
    - 10 second timeout for API, 30s for downloads
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

try:
    from secrets import GITHUB_TOKEN
except ImportError:
    GITHUB_TOKEN = None


def get_headers() -> dict:
    """Get HTTP headers with optional auth token."""
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def get_latest_release(owner: str, repo: str) -> dict | None:
    """Fetch latest release info from GitHub API."""
    if requests is None:
        log("urequests not available")
        return None

    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        response = requests.get(url, headers=get_headers(), timeout=10)

        if response.status_code == 200:
            data = ujson.loads(response.text)
            assets = data.get("assets", [])
            if not assets:
                log("Release has no files attached")
                return None
            return {
                "tag": data.get("tag_name", "").lstrip("v"),
                "name": data.get("name", ""),
                "assets": assets,
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
        blink_pattern("111")
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
            response = requests.get(url, headers=get_headers(), timeout=30)

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
        blink_pattern("111")
        return False

    cleanup_backup()
    log(f"Updated {files_updated} files")
    blink_pattern("11011")
    return True


def check_and_update(owner: str, repo: str) -> bool:
    """Check for updates from GitHub and apply if available."""
    if not is_connected():
        log("WiFi not connected")
        return False

    log("Checking GitHub for updates...")
    blink_pattern("11")

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
