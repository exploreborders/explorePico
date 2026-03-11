"""
main.py - Entry Point for Pico 2W MQTT Client

This is the main entry point that runs on boot. It handles firmware updates
before launching the main application.

Update Priority:
    1. GitHub updates (if enabled and WiFi available)
    2. Launch main application

Rollback:
    Press the update button twice within 2 seconds at boot to trigger
    a rollback to the previous firmware version.

Usage:
    Upload all .py files to Pico flash. On reset, this file runs first.
    It will check for updates and then launch the application automatically.

Configuration:
    Update behavior is controlled by config.py settings:
    - GITHUB_OWNER, GITHUB_REPO: GitHub repository for updates
    - UPDATE_BUTTON_PIN: GPIO pin for rollback trigger (default: 10)
"""

import sys
import machine

from wifi_utils import scan_and_connect
from updater_utils import log, detect_rollback_trigger, perform_rollback

try:
    from config import (
        GITHUB_OWNER,
        GITHUB_REPO,
        WIFI_SSID,
        WIFI_PASSWORD,
        WIFI_SSID_2,
        WIFI_PASSWORD_2,
        UPDATE_BUTTON_PIN,
    )

    GITHUB_UPDATES_ENABLED = True
except Exception:
    GITHUB_UPDATES_ENABLED = False


github_updated = False
update_check_executed = False

# Check for rollback trigger FIRST (before any updates)
if GITHUB_UPDATES_ENABLED:
    try:
        if detect_rollback_trigger(UPDATE_BUTTON_PIN):
            log("Rollback triggered!")
            if perform_rollback():
                log("Rebooting...")
                machine.reset()
    except Exception as e:
        log(f"Rollback check failed: {e}")

if GITHUB_UPDATES_ENABLED:
    log("Connecting to WiFi...")
    # Build list of networks to try
    networks = [(WIFI_SSID, WIFI_PASSWORD)]
    if WIFI_SSID_2 and WIFI_PASSWORD_2:
        networks.append((WIFI_SSID_2, WIFI_PASSWORD_2))

    if scan_and_connect(networks):
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

try:
    import app

    app.main()
except Exception as e:
    log(f"Main failed: {e}")
    sys.exit(1)
