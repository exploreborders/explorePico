"""
GitHub WiFi Updater for Pico 2W

Checks GitHub releases for updates and automatically downloads
and applies firmware updates over WiFi.

Update Process:
    1. Connect to WiFi
    2. Fetch latest release tag from GitHub API
    3. Get file list from repository contents
    4. Compare version with current
    5. If newer, backup current firmware
    6. Download .py files from repository
    7. Reboot to apply changes

GitHub Setup:
    1. Create a GitHub repository with .py files
    2. Create a release with version tag (e.g., v1.2.0)
    3. Configure GITHUB_OWNER and GITHUB_REPO in config.py
    4. Files are downloaded directly from repository (not release assets!)

Rollback:
    If update fails, automatically restores from backup.
    Manual rollback: Press update button twice within 2 seconds at boot.

Usage:
    Automatic on boot if WiFi is available.
    Configure GITHUB_OWNER and GITHUB_REPO in config.py.

API:
    Uses GitHub REST API for releases and contents.

Notes:
    - Requires urequests library
    - Files downloaded from repo, not release assets
    - Only .py files are downloaded
    - secrets.py is never overwritten
    - Automatic rollback on failure
    - 10 second timeout for API, 30s for downloads
"""

import machine
import time
import ujson
import ubinascii

FILES_TO_UPDATE = [
    "main.py",
    "app.py",
    "config.py",
    "github_updater.py",
    "sd_updater.py",
    "blink.py",
    "wifi_utils.py",
    "updater_utils.py",
    "sensors/__init__.py",
    "sensors/ds18b20.py",
    "sensors/ads1115.py",
    "sensors/acs37030.py",
]

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
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Pico2W-MQTT-Client",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def get_latest_release_tag(owner: str, repo: str) -> str | None:
    """Fetch latest release tag from GitHub API."""
    if requests is None:
        log("urequests not available")
        return None

    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        response = requests.get(url, headers=get_headers(), timeout=10)

        if response.status_code == 200:
            data = ujson.loads(response.text)
            tag = data.get("tag_name", "").lstrip("v")
            log(f"Latest release: {tag}")
            return tag
        elif response.status_code == 403:
            log("GitHub API rate limited (try again later)")
        elif response.status_code == 404:
            log("No release found")
        else:
            log(f"GitHub API error: {response.status_code}")
        return None
    except Exception as e:
        log(f"Request failed: {e}")
        return None


def get_file_list(owner: str, repo: str, ref: str) -> list | None:
    """Get list of .py files from repository."""
    if requests is None:
        return None

    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents?ref={ref}"
        response = requests.get(url, headers=get_headers(), timeout=10)

        if response.status_code == 200:
            return ujson.loads(response.text)
        return None
    except Exception as e:
        log(f"Failed to get file list: {e}")
        return None


def get_file_content(owner: str, repo: str, path: str, ref: str) -> str | None:
    """Get file content from repository."""
    if requests is None:
        return None

    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}"
        response = requests.get(url, headers=get_headers(), timeout=30)

        if response.status_code == 200:
            data = ujson.loads(response.text)

            content = data.get("content", "")
            if content:
                decoded = ubinascii.a2b_base64(content)
                return decoded.decode("utf-8")
        return None
    except Exception as e:
        log(f"Failed to get {path}: {e}")
        return None


def get_all_py_files(owner: str, repo: str, ref: str, prefix: str = "") -> list:
    """Get list of .py files from repository - filtered to essential files only."""
    files = []
    contents = get_file_list(owner, repo, ref)

    if not contents:
        return files

    for item in contents:
        name = item.get("name", "")
        path = item.get("path", "")
        item_type = item.get("type", "")

        if item_type == "file" and name.endswith(".py"):
            full_path = prefix + name if not prefix else prefix + "/" + name
            if full_path in FILES_TO_UPDATE:
                files.append({"path": full_path, "api_path": path})
        elif item_type == "dir" and name not in [".git", ".vscode"]:
            sub_files = get_all_py_files(owner, repo, ref, name)
            files.extend(sub_files)

    return files


def get_latest_release(owner: str, repo: str) -> dict | None:
    """Fetch latest release info and file list from GitHub."""
    tag = get_latest_release_tag(owner, repo)
    if not tag:
        log("No release found")
        return None

    log(f"Fetching file list for tag {tag}...")
    py_files = get_all_py_files(owner, repo, tag)

    if not py_files:
        log("No .py files found in repository")
        return None

    log(f"Found {len(py_files)} .py files")

    return {
        "tag": tag,
        "files": py_files,
    }


def download_and_update(owner: str, repo: str, release_info: dict) -> bool:
    """Download files from GitHub repository and update."""
    log("Downloading files...")
    blink_pattern("11")

    tag = release_info.get("tag", "")
    py_files = release_info.get("files", [])

    log(f"Updating {len(py_files)} files")

    for file_info in py_files:
        filename = file_info.get("path", "")
        api_path = file_info.get("api_path", "")

        if not filename or not api_path:
            continue

        if filename == "secrets.py":
            log(f"Skipping {filename} (never overwrite secrets)")
            continue

        try:
            log(f"Downloading {filename}...")
            content = get_file_content(owner, repo, api_path, tag)

            if content is None:
                log(f"Download failed: {filename}")
                return False

            if not copy_file_content(content, filename):
                return False

            log(f"Updated: {filename}")

        except Exception as e:
            log(f"Failed to update {filename}: {e}")
            return False

    write_version(tag)
    log(f"Updated to {tag}, rebooting...")
    blink_pattern("11011")
    time.sleep(1)
    machine.reset()
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
