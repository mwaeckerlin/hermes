"""Shared settings of the browser suite: addresses, readiness, the login.

The dashboard asks for a login before it serves its interface. Every login of
the suite happens once per session and address (the password provider counts
attempts), and the tests open their pages in the signed-in browser context.
"""
import os
import time
from urllib.parse import urlparse

import pytest
import requests

PROXY_URL = os.environ.get("PROXY_URL", "http://proxy:8080").rstrip("/")
PREFIX = os.environ.get("PREFIX", "/hermes")
ROOT_URL = os.environ.get("ROOT_URL", "http://dashboard-root:9119").rstrip("/")
USERNAME = os.environ["DASHBOARD_USERNAME"]
PASSWORD = os.environ["DASHBOARD_PASSWORD"]
APP = PROXY_URL + PREFIX + "/"

# every root-absolute URL the rendered document names, in any element
ROOT_ABSOLUTE_URLS = """() => [...document.querySelectorAll('[src],[href],[action]')]
    .flatMap(element => ['src', 'href', 'action'].map(name => element.getAttribute(name)))
    .filter(value => value && value.startsWith('/') && !value.startsWith('//'))"""


def wait_for(url, timeout=300):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return
            last = f"status {response.status_code}: {response.text[:200]}"
        except requests.RequestException as error:
            last = error
        time.sleep(2)
    raise TimeoutError(f"{url} did not answer 200 within {timeout}s: {last}")


def below(url, prefix=PREFIX):
    path = urlparse(url).path
    return path == prefix or path.startswith(prefix + "/")


def own(urls, origin):
    netloc = urlparse(origin).netloc
    return [url for url in urls if urlparse(url).scheme in ("http", "https", "ws", "wss") and urlparse(url).netloc == netloc]


def outside(urls, origin=PROXY_URL, prefix=PREFIX):
    return [url for url in own(urls, origin) if not below(url, prefix)]


def record(page):
    """Every request, response and websocket of the page, from now on."""
    requested, responses = [], {}
    page.on("request", lambda request: requested.append(request.url))
    page.on("response", lambda response: responses.__setitem__(response.url, response.status))
    page.on("websocket", lambda websocket: requested.append(websocket.url))
    return requested, responses


def mounted(page):
    page.wait_for_function("document.getElementById('root') && document.getElementById('root').children.length > 0", timeout=60000)


def sign_in(page, origin, prefix):
    """The login of an operator: the dashboard sends him to its login page,
    he enters user name and password, and the dashboard opens."""
    page.goto(origin + prefix + "/")
    page.wait_for_url(lambda url: urlparse(url).path == prefix + "/login", timeout=60000)
    page.fill("input[name=username]", USERNAME)
    page.fill("input[name=password]", PASSWORD)
    with page.expect_response(lambda response: urlparse(response.url).path == prefix + "/auth/password-login") as answer:
        page.get_by_role("button", name="Sign in", exact=True).click()
    assert answer.value.ok, f"the login answered {answer.value.status}: {answer.value.text()[:300]}"
    page.wait_for_url(lambda url: urlparse(url).path != prefix + "/login", timeout=60000)
    mounted(page)
    page.wait_for_load_state("networkidle")


def api_session(origin, prefix):
    """A requests session logged in the way the login page logs in."""
    session = requests.Session()
    response = session.post(origin + prefix + "/auth/password-login", timeout=30,
                            json={"provider": "basic", "username": USERNAME, "password": PASSWORD})
    assert response.status_code == 200 and response.json().get("ok"), f"login answered {response.status_code}: {response.text[:300]}"
    return session


@pytest.fixture(scope="session", autouse=True)
def services_ready():
    wait_for(PROXY_URL + PREFIX + "/login")
    wait_for(ROOT_URL + "/login")


def _signed_in(browser, origin, prefix):
    context = browser.new_context()
    page = context.new_page()
    requested, responses = record(page)
    sign_in(page, origin, prefix)
    return context, {"requested": list(requested), "responses": dict(responses), "url": page.url}


@pytest.fixture(scope="session")
def signed_in_below_base_path(browser):
    """The browser context of the operator signed in below the base path, with
    every request the page made from the first address to the open dashboard."""
    context, visit = _signed_in(browser, PROXY_URL, PREFIX)
    yield context, visit
    context.close()


@pytest.fixture(scope="session")
def signed_in_at_root(browser):
    context, visit = _signed_in(browser, ROOT_URL, "")
    yield context, visit
    context.close()


@pytest.fixture(scope="session")
def api_below_base_path():
    return api_session(PROXY_URL, PREFIX)


@pytest.fixture(scope="session")
def api_at_root():
    return api_session(ROOT_URL, "")
