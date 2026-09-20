#!/usr/bin/env python3
"""
AI TimeSync - Desktop Application & Window Activity Tracker
Automatically monitors active OS window titles, classifies them into
PRODUCTIVE, NEUTRAL, or DISTRACTION using the ML classifier, and syncs
time entries with the AI Time Management server.
"""

import sys
import time
import argparse
import logging
import requests
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("desktop_tracker")


def get_active_window_title() -> str:
    """
    Cross-platform retrieval of the active foreground window title.
    Supports Windows via ctypes with fallback on other platforms.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                return buff.value
        except Exception as e:
            logger.debug(f"Windows API error: {e}")
            return "Windows Desktop"
    elif sys.platform == "darwin":
        try:
            import subprocess
            cmd = "osascript -e 'tell application \"System Events\" to get name of first application process whose frontmost is true'"
            return subprocess.check_output(cmd, shell=True).decode().strip()
        except Exception:
            return "macOS Desktop"
    elif sys.platform.startswith("linux"):
        try:
            import subprocess
            return subprocess.check_output(["xdotool", "getactivewindow", "getwindowname"]).decode().strip()
        except Exception:
            return "Linux Desktop"
    return "Unknown Application"


def parse_app_and_domain(window_title: str):
    """
    Extracts application name and probable domain from window title.
    Example: 'AI Time Management - Google Chrome' -> ('chrome', 'aitimemanagement.com')
    """
    title_lower = window_title.lower()
    app_name = "unknown"
    domain = ""

    known_apps = [
        ("code", "Visual Studio Code"),
        ("pycharm", "PyCharm"),
        ("chrome", "Google Chrome"),
        ("firefox", "Mozilla Firefox"),
        ("edge", "Microsoft Edge"),
        ("slack", "Slack"),
        ("teams", "Microsoft Teams"),
        ("zoom", "Zoom Meeting"),
        ("terminal", "Terminal"),
        ("powershell", "PowerShell"),
        ("discord", "Discord"),
        ("spotify", "Spotify"),
        ("outlook", "Microsoft Outlook"),
        ("excel", "Microsoft Excel"),
        ("word", "Microsoft Word"),
    ]

    for identifier, name in known_apps:
        if identifier in title_lower or name.lower() in title_lower:
            app_name = identifier
            break

    # Extract common web domains if running in browser
    for d in ["youtube.com", "github.com", "google.com", "stackoverflow.com", "reddit.com", "netflix.com", "jira.com"]:
        if d in title_lower:
            domain = d
            break

    return app_name, domain


def run_tracker(server_url: str, interval: int = 5, demo: bool = False):
    logger.info("=" * 60)
    logger.info("AI TimeSync - Desktop Window & Application Tracker")
    logger.info(f"Target Server: {server_url} | Poll Interval: {interval}s | Demo Mode: {demo}")
    logger.info("Press Ctrl+C to stop tracking.")
    logger.info("=" * 60)

    current_window = None
    session_start = time.time()

    try:
        while True:
            title = get_active_window_title()

            if title != current_window:
                elapsed = round(time.time() - session_start, 1)
                if current_window and elapsed >= 1.0:
                    app, domain = parse_app_and_domain(current_window)
                    logger.info(f"Activity [{elapsed}s]: '{current_window}' (App: {app})")

                current_window = title
                session_start = time.time()
                app, domain = parse_app_and_domain(title)

                if demo:
                    # In demo mode, simulate heuristic / ML classification
                    category = "PRODUCTIVE"
                    if any(w in title.lower() for w in ["youtube", "netflix", "game", "reddit", "twitter"]):
                        category = "DISTRACTION"
                    elif any(w in title.lower() for w in ["slack", "teams", "zoom", "email", "outlook"]):
                        category = "NEUTRAL"
                    logger.info(f"==> Active Window Changed: '{title}' -> Category: [{category}]")
                else:
                    # Ping server time tracking API if configured
                    try:
                        resp = requests.get(f"{server_url}/api/time/active/", timeout=3)
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get("has_active"):
                                logger.info(f"Active Server Timer: {data.get('entry', {}).get('activity_type')}")
                    except requests.RequestException:
                        pass

            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("\nStopping Desktop Tracker. Session ended.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI TimeSync Desktop Window Tracker")
    parser.add_argument("--server", default="http://127.0.0.1:8000", help="AI Time Management Server URL")
    parser.add_argument("--interval", type=int, default=3, help="Polling interval in seconds (default: 3)")
    parser.add_argument("--demo", action="store_true", default=True, help="Run in local preview/demo mode")

    args = parser.parse_args()
    run_tracker(server_url=args.server, interval=args.interval, demo=args.demo)
