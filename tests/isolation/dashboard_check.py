"""Runs inside the dashboard container (tests/run-isolation.sh pipes it in):
the key page refuses a request without login, and after login it shows no
secret of the gateway.

Usage: python3 - <username> <password> <marker> …   (markers: strings that must not appear)
"""
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:9119"
username, password, markers = sys.argv[1], sys.argv[2], sys.argv[3:]

try:
    urllib.request.urlopen(f"{BASE}/api/env", timeout=30).close()
    sys.exit("FAIL  dashboard_requires_login: /api/env answered without login")
except urllib.error.HTTPError as refused:
    refused.close()
    if refused.code not in (401, 403):
        sys.exit(f"FAIL  dashboard_requires_login: /api/env answered {refused.code} without login")
print("PASS  dashboard_requires_login")

opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
login = urllib.request.Request(f"{BASE}/auth/password-login", method="POST", headers={"Content-Type": "application/json"},
                               data=json.dumps({"provider": "basic", "username": username, "password": password}).encode())
with opener.open(login, timeout=30) as response:
    assert json.load(response).get("ok"), "login failed"
with opener.open(f"{BASE}/api/env", timeout=30) as response:
    page = response.read().decode()
leaked = [marker for marker in markers if marker and marker in page]
if leaked:
    sys.exit(f"FAIL  dashboard_shows_no_secret: /api/env shows {leaked}")
print("PASS  dashboard_shows_no_secret")
