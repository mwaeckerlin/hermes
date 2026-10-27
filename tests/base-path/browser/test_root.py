"""The same image without HERMES_BASE_PATH: the dashboard at the root, as
before, in Chromium."""
from urllib.parse import urlparse

import requests

from conftest import PREFIX, ROOT_ABSOLUTE_URLS, ROOT_URL, mounted, own, record


def prefixed(urls):
    return [url for url in own(urls, ROOT_URL) if urlparse(url).path.startswith(PREFIX + "/")]


def test_login_redirect_at_the_root():
    response = requests.get(ROOT_URL + "/sessions", allow_redirects=False, timeout=10)
    assert response.status_code in (302, 303, 307), response.status_code
    assert urlparse(response.headers["Location"]).path == "/login"


def test_the_page_names_its_assets_at_the_root(api_at_root):
    page = api_at_root.get(ROOT_URL + "/", timeout=10)
    assert page.status_code == 200, page.status_code
    assert 'src="/assets/' in page.text
    assert 'window.__HERMES_BASE_PATH__=""' in page.text


def test_sign_in_opens_the_dashboard_at_the_root(signed_in_at_root):
    _, visit = signed_in_at_root
    requested = own(visit["requested"], ROOT_URL)
    assert requested, "the page made no request to its own server"
    assert not prefixed(requested), f"the root asked for {PREFIX}: {prefixed(requested)}"
    assets = {url: status for url, status in visit["responses"].items() if urlparse(url).path.startswith("/assets/")}
    assert assets and set(assets.values()) == {200}, f"assets at the root: {assets}"
    assert urlparse(visit["url"]).path != "/login", visit["url"]


def test_plugin_tab_at_the_root(signed_in_at_root):
    context, _ = signed_in_at_root
    page = context.new_page()
    requested, _ = record(page)
    with page.expect_response(lambda response: urlparse(response.url).path == "/api/plugins/todo/list") as answer:
        page.goto(ROOT_URL + "/todo")
    assert answer.value.status == 200, answer.value.status
    mounted(page)
    page.wait_for_load_state("networkidle")
    named = [url for url in page.evaluate(ROOT_ABSOLUTE_URLS) if url.startswith(PREFIX + "/")]
    page.close()
    assert not named, f"the root page names {named}"
    assert not prefixed(requested), prefixed(requested)
