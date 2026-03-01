"""
boot.py - Entry Point for Pico 2W MQTT Client

This is the main entry point that runs on boot. It handles firmware updates
before launching the main application.

Update Priority:
    1. GitHub updates (if enabled and WiFi available)
    2. SD card updates (if no GitHub update)
    3. Launch main application

Rollback:
    Press the update button twice within 2 seconds at boot to trigger
    a rollback to the previous firmware version.

Usage:
    Upload all .py files to Pico flash. On reset, this file runs first.
    It will check for updates and then launch main.py automatically.

Configuration:
    Update behavior is controlled by config.py settings:
    - GITHUB_OWNER, GITHUB_REPO: GitHub repository for updates
    - UPDATE_BUTTON_PIN: GPIO pin for rollback trigger (default: 10)
"""

import sys

from wifi_utils import connect
from updater_utils import log

try:
    from config import (
        GITHUB_OWNER,
        GITHUB_REPO,
        WIFI_SSID,
        WIFI_PASSWORD,
    )

    GITHUB_UPDATES_ENABLED = True
except Exception:
    GITHUB_UPDATES_ENABLED = False


github_updated = False
sd_updated = False
update_check_executed = False

if GITHUB_UPDATES_ENABLED:
    log("Connecting to WiFi...")
    if connect(WIFI_SSID, WIFI_PASSWORD):
        log("WiFi connected!")
        try:
            from github_updater import check_and_update

            log("Checking GitHub for updates...")
            update_check_executed = True
            github_updated = check_and_update(GITHUB_OWNER, GITHUB_REPO)

            # Note: If github_updated is True, download_and_update()
            # already called machine.reset() - we never reach here
            if github_updated:
                log("GitHub update applied, rebooting...")
            else:
                log("No GitHub update available")
        except Exception as e:
            log(f"GitHub update check failed: {e}")
    else:
        log("WiFi connection failed")

if not github_updated and not update_check_executed:
    try:
        from sd_updater import check_and_apply_update

        log("Checking SD card for updates...")
        sd_updated = check_and_apply_update()

        if sd_updated:
            log("SD update applied, rebooting...")
    except Exception as e:
        log(f"SD update check failed: {e}")

try:
    import app

    app.main()
except Exception as e:
    log(f"Main failed: {e}")
    sys.exit(1)
