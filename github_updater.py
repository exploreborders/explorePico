"""
GitHub WiFi Updater for Pico 2W

Checks GitHub releases for updates and automatically downloads
and applies firmware updates over WiFi.
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
            log("GitHub API rate limited")
        elif response.status_code == 404:
            log("No release found")
        else:
            log(f"GitHub API error: {response.status_code}")
        return None
    except Exception as e:
        log(f"Request failed: {e}")
        return None


def get_file_list(owner: str, repo: str, ref: str) -> list | None:
    """Get list of files from repository."""
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


def get_raw_url(owner: str, repo: str, path: str, ref: str) -> str:
    """Generate raw GitHub URL for a file."""
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"


def get_all_files(owner: str, repo: str, ref: str, seen: set = None) -> list:
    """Recursively get all .py and version.txt files from repository."""
    if seen is None:
        seen = set()

    files = []
    contents = get_file_list(owner, repo, ref)

    if not contents:
        return files

    for item in contents:
        name = item.get("name", "")
        path = item.get("path", "")
        item_type = item.get("type", "")

        if item_type == "file" and (name.endswith(".py") or name == "version.txt"):
            if path in seen:
                continue
            seen.add(path)
            files.append({"path": path, "raw_url": get_raw_url(owner, repo, path, ref)})
        elif item_type == "dir" and name not in [".git", ".vscode", "__pycache__"]:
            # Recursively get files from subdirectory
            sub_path = f"{ref}/{name}" if ref else name
            sub_files = get_all_files(owner, repo, sub_path, seen)
            files.extend(sub_files)

    return files


def download_file(url: str) -> str | None:
    """Download file content from raw URL."""
    if requests is None:
        return None

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.text
        return None
    except Exception as e:
        log(f"Download failed: {e}")
        return None


def get_latest_release(owner: str, repo: str) -> dict | None:
    """Fetch latest release info and file list from GitHub."""
    tag = get_latest_release_tag(owner, repo)
    if not tag:
        log("No release found")
        return None

    log(f"Fetching file list for tag {tag}...")
    files = get_all_files(owner, repo, tag)

    if not files:
        log("No files found in repository")
        return None

    log(f"Found {len(files)} files to update")

    return {
        "tag": tag,
        "files": files,
    }


def download_and_update(owner: str, repo: str, release_info: dict) -> bool:
    """Download files from GitHub repository and update."""
    log("Downloading files...")
    blink_pattern("11")

    tag = release_info.get("tag", "")
    files = release_info.get("files", [])

    log(f"Updating {len(files)} files")

    for file_info in files:
        filename = file_info.get("path", "")
        raw_url = file_info.get("raw_url", "")

        if not filename or not raw_url:
            continue

        if filename == "secrets.py":
            log(f"Skipping {filename}")
            continue

        try:
            log(f"Downloading {filename}...")
            content = download_file(raw_url)

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
        return True

    return False
