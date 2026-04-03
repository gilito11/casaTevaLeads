#!/usr/bin/env python3
"""
Quick proxy health check. Tests IPRoyal proxy connectivity.
Exits 0 if proxy works, 1 if failed (402 Payment Required = credit exhausted).
Sends Telegram alert on failure.
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def check_proxy():
    proxy_str = os.environ.get('DATADOME_PROXY', '')
    if not proxy_str:
        print("DATADOME_PROXY not set - skipping proxy check")
        return 0

    # Parse proxy string (user:pass@host:port)
    try:
        if "@" in proxy_str:
            auth, addr = proxy_str.rsplit("@", 1)
            proxy_url = f"http://{auth}@{addr}"
        else:
            proxy_url = f"http://{proxy_str}"
    except Exception as e:
        print(f"Invalid proxy format: {e}")
        return 1

    import requests
    try:
        resp = requests.get(
            "https://httpbin.org/ip",
            proxies={"https": proxy_url, "http": proxy_url},
            timeout=15,
        )
        if resp.status_code == 200:
            ip = resp.json().get("origin", "unknown")
            print(f"Proxy OK - IP: {ip}")
            return 0
        elif resp.status_code == 402:
            msg = "IPRoyal proxy credit exhausted (402 Payment Required). Recharge at iproyal.com"
            print(f"PROXY FAILED: {msg}")
            _send_alert(msg)
            return 1
        else:
            msg = f"Proxy returned HTTP {resp.status_code}"
            print(f"PROXY FAILED: {msg}")
            _send_alert(msg)
            return 1
    except requests.exceptions.ProxyError as e:
        error_str = str(e)
        if "402" in error_str or "Payment Required" in error_str:
            msg = "IPRoyal proxy credit exhausted (402 Payment Required). Recharge at iproyal.com"
        else:
            msg = f"Proxy connection failed: {error_str[:200]}"
        print(f"PROXY FAILED: {msg}")
        _send_alert(msg)
        return 1
    except Exception as e:
        msg = f"Proxy check error: {e}"
        print(f"PROXY FAILED: {msg}")
        _send_alert(msg)
        return 1


def _send_alert(message):
    try:
        from scrapers.utils.telegram_alerts import send_telegram_alert
        send_telegram_alert(f"<b>Proxy Alert</b>\n\n{message}")
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(check_proxy())
