"""
boot.py - Entry point for Pico 2W
Handles SD card updates before launching main app
"""

import sys

try:
    from sd_updater import check_and_apply_update

    check_and_apply_update()
except Exception as e:
    print(f"[BOOT] Update check failed: {e}")

try:
    import main

    main.main()
except Exception as e:
    print(f"[BOOT] Main failed: {e}")
    sys.exit(1)
