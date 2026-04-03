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

from updater_utils import (
    log,
    read_version,
    write_version,
    compare_versions,
    copy_file_content,
)

try:
    from lte_utils import is_lte_connected
except Exception:
    is_lte_connected = None

_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Pico2W-MQTT-Client",
}


def get_latest_release_tag(owner: str, repo: str) -> str | None:
    """Fetch latest release tag from GitHub API."""
    if requests is None:
        log("urequests not available")
        return None

    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        response = requests.get(url, headers=_HEADERS, timeout=10)

        if response.status_code == 200:
            data = ujson.loads(response.text)
            tag = data.get("tag_name", "").lstrip("v")
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


def get_file_list(owner: str, repo: str, ref: str, path: str = "") -> list | None:
    """Get list of files from repository at the given path."""
    if requests is None:
        return None

    try:
        content_path = f"/{path}" if path else ""
        url = f"https://api.github.com/repos/{owner}/{repo}/contents{content_path}?ref={ref}"
        response = requests.get(url, headers=_HEADERS, timeout=10)

        if response.status_code == 200:
            return ujson.loads(response.text)
        return None
    except Exception as e:
        log(f"Failed to get file list: {e}")
        return None


def get_raw_url(owner: str, repo: str, path: str, ref: str) -> str:
    """Generate raw GitHub URL for a file."""
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"


def get_all_files(owner: str, repo: str, ref: str, seen: set = None, path: str = "") -> list:
    """Recursively get all .py and version.txt files from repository."""
    if seen is None:
        seen = set()

    files = []
    contents = get_file_list(owner, repo, ref, path)

    if not contents:
        return files

    for item in contents:
        name = item.get("name", "")
        item_path = item.get("path", "")
        item_type = item.get("type", "")

        if item_type == "file" and (name.endswith(".py") or name == "version.txt"):
            if item_path in seen:
                continue
            seen.add(item_path)
            files.append({"path": item_path, "raw_url": get_raw_url(owner, repo, item_path, ref)})
        elif item_type == "dir" and name not in [".git", ".vscode", "__pycache__"]:
            dir_path = f"{path}/{name}" if path else name
            sub_files = get_all_files(owner, repo, ref, seen, dir_path)
            files.extend(sub_files)

    return files


def download_file(url: str) -> str | None:
    """Download file content from raw URL."""
    if requests is None:
        return None

    try:
        response = requests.get(url, headers=_HEADERS, timeout=30)
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


def download_and_update(
    owner: str,
    repo: str,
    release_info: dict,
    progress_callback=None,
) -> bool:
    """Download files from GitHub repository and update.

    Args:
        owner: GitHub repository owner
        repo: GitHub repository name
        release_info: Dict with 'tag' and 'files' keys
        progress_callback: Optional callback(percent: int, status: str) -> None
    """
    log("Downloading files...")

    tag = release_info.get("tag", "")
    files = release_info.get("files", [])

    log(f"Updating {len(files)} files")

    for idx, file_info in enumerate(files):
        filename = file_info.get("path", "")
        raw_url = file_info.get("raw_url", "")

        if not filename or not raw_url:
            continue

        if filename == "secrets.py":
            log(f"Skipping {filename}")
            continue

        content = download_file(raw_url)
        if content is None:
            log(f"Download failed: {filename}")
            if progress_callback:
                progress_callback(0, "error")
            return False

        if not copy_file_content(content, filename):
            log(f"Write failed: {filename}")
            if progress_callback:
                progress_callback(0, "error")
            return False

        log(f"Updated: {filename}")

        if progress_callback:
            progress_callback(int((idx + 1) * 90 / len(files)), "downloading")

    write_version(tag)
    log(f"Updated to {tag}")

    if progress_callback:
        progress_callback(95, "rebooting")

    time.sleep(0.5)
    machine.reset()
    return True


def check_and_update(owner: str, repo: str, progress_callback=None) -> bool:
    """Check for updates from GitHub and apply if available.

    Args:
        owner: GitHub repository owner
        repo: GitHub repository name
        progress_callback: Optional callback(percent: int, status: str) -> None

    Returns:
        True if update was applied and device will reboot
    """
    from wifi_utils import is_connected

    if not is_connected() and not (is_lte_connected and is_lte_connected()):
        log("No network connection (WiFi/LTE)")
        if progress_callback:
            progress_callback(0, "error")
        return False

    log("Checking GitHub for updates...")

    new_version = get_latest_release_tag(owner, repo)
    if not new_version:
        log("No release found or API error")
        if progress_callback:
            progress_callback(0, "error")
        return False

    log(f"Latest release: {new_version}")

    current = read_version() or "0.0"
    log(f"Current: {current}, Latest: {new_version}")

    result = compare_versions(current, new_version)

    if result <= 0:
        log("No update needed")
        if progress_callback:
            progress_callback(100, "up_to_date")
        return False

    log(f"Update available: {new_version}")

    release = get_latest_release(owner, repo)
    if not release:
        log("Failed to get release info")
        if progress_callback:
            progress_callback(0, "error")
        return False

    if download_and_update(owner, repo, release, progress_callback):
        return True

    return False
