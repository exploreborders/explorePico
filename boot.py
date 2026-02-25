"""
boot.py - Entry point for Pico 2W
Handles GitHub and SD card updates before launching main app
"""

import sys

from wifi_utils import connect
from updater_utils import set_logger, log


set_logger(lambda tag, msg: print(f"[{tag}] {msg}"), "BOOT")

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

if GITHUB_UPDATES_ENABLED:
    log("Connecting to WiFi...")
    if connect(WIFI_SSID, WIFI_PASSWORD):
        log("WiFi connected!")
        try:
            from github_updater import check_and_update

            log("Checking GitHub for updates...")
            github_updated = check_and_update(GITHUB_OWNER, GITHUB_REPO)

            if github_updated:
                log("GitHub update applied, rebooting...")
        except Exception as e:
            log(f"GitHub update check failed: {e}")
    else:
        log("WiFi connection failed")

if not github_updated:
    try:
        from sd_updater import check_and_apply_update

        log("Checking SD card for updates...")
        sd_updated = check_and_apply_update()

        if sd_updated:
            log("SD update applied, rebooting...")
    except Exception as e:
        log(f"SD update check failed: {e}")

try:
    import main

    main.main()
except Exception as e:
    log(f"Main failed: {e}")
    sys.exit(1)
