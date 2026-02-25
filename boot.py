"""
boot.py - Entry point for Pico 2W
Handles GitHub and SD card updates before launching main app
"""

import sys

from wifi_utils import connect
from updater_utils import set_logger


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
    print("[BOOT] Connecting to WiFi...")
    if connect(WIFI_SSID, WIFI_PASSWORD):
        print("[BOOT] WiFi connected!")
        try:
            from github_updater import check_and_update

            print("[BOOT] Checking GitHub for updates...")
            github_updated = check_and_update(GITHUB_OWNER, GITHUB_REPO)

            if github_updated:
                print("[BOOT] GitHub update applied, rebooting...")
        except Exception as e:
            print(f"[BOOT] GitHub update check failed: {e}")
    else:
        print("[BOOT] WiFi connection failed")

if not github_updated:
    try:
        from sd_updater import check_and_apply_update

        print("[BOOT] Checking SD card for updates...")
        sd_updated = check_and_apply_update()
    except Exception as e:
        print(f"[BOOT] SD update check failed: {e}")

try:
    import main

    main.main()
except Exception as e:
    print(f"[BOOT] Main failed: {e}")
    sys.exit(1)
