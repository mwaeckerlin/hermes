"""Runs inside the dashboard container (tests/run-isolation.sh pipes it in).

login: the key page refuses a request without login; the login with the
password of the Docker secret succeeds, and logged in, the key page shows no
secret of the gateway. Prints the session cookie as `COOKIE <header value>`.

session: the session cookie of the login before the restart still opens the
key page, so the token was signed with the session secret of the Docker secret
and not with a key drawn at start.

Usage: python3 - login <username> <password> <marker> …   (markers: strings that must not appear)
       python3 - session <cookie header value>
"""
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:9119"
mode = sys.argv[1]

if mode == "session":
    request = urllib.request.Request(f"{BASE}/api/env", headers={"Cookie": sys.argv[2]})
    try:
        urllib.request.urlopen(request, timeout=30).close()
    except urllib.error.HTTPError as refused:
        refused.close()
        sys.exit(f"FAIL  dashboard_session_survives_restart: /api/env answered {refused.code} to the session of before the restart")
    print("PASS  dashboard_session_survives_restart")
    sys.exit(0)

username, password, markers = sys.argv[2], sys.argv[3], sys.argv[4:]

try:
    urllib.request.urlopen(f"{BASE}/api/env", timeout=30).close()
    sys.exit("FAIL  dashboard_requires_login: /api/env answered without login")
except urllib.error.HTTPError as refused:
    refused.close()
    if refused.code not in (401, 403):
        sys.exit(f"FAIL  dashboard_requires_login: /api/env answered {refused.code} without login")
print("PASS  dashboard_requires_login")

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
login = urllib.request.Request(f"{BASE}/auth/password-login", method="POST", headers={"Content-Type": "application/json"},
                               data=json.dumps({"provider": "basic", "username": username, "password": password}).encode())
try:
    with opener.open(login, timeout=30) as response:
        if not json.load(response).get("ok"):
            sys.exit("FAIL  dashboard_login_from_secret: the login with the password of the Docker secret was refused")
except urllib.error.HTTPError as refused:
    refused.close()
    sys.exit(f"FAIL  dashboard_login_from_secret: the login with the password of the Docker secret answered {refused.code}")
print("PASS  dashboard_login_from_secret")

with opener.open(f"{BASE}/api/env", timeout=30) as response:
    page = response.read().decode()
leaked = [marker for marker in markers if marker and marker in page]
if leaked:
    sys.exit(f"FAIL  dashboard_shows_no_secret: /api/env shows {leaked}")
print("PASS  dashboard_shows_no_secret")
print("COOKIE " + "; ".join(f"{cookie.name}={cookie.value}" for cookie in jar))
