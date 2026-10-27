"""The dashboard below the base path /hermes, behind Traefik with
PathPrefix(`/hermes`) and without StripPrefix, in Chromium."""
from urllib.parse import urlparse

import requests

from conftest import APP, PREFIX, PROXY_URL, ROOT_ABSOLUTE_URLS, below, mounted, outside, own, record


def test_bare_base_path_redirects_to_its_slash_form():
    for request, location in ((PREFIX, PREFIX + "/"), (PREFIX + "?next=%2F", PREFIX + "/?next=%2F")):
        response = requests.get(PROXY_URL + request, allow_redirects=False, timeout=10)
        assert response.status_code == 308, response.status_code
        assert response.headers["Location"] == location


def test_nothing_outside_the_base_path_is_routed():
    assert requests.get(PROXY_URL + "/login", timeout=10).status_code == 404


def test_login_redirect_stays_below_the_base_path():
    response = requests.get(APP + "sessions", allow_redirects=False, timeout=10)
    assert response.status_code in (302, 303, 307), response.status_code
    assert below(response.headers["Location"]), response.headers["Location"]
    assert urlparse(response.headers["Location"]).path == PREFIX + "/login"


def test_login_page_posts_below_the_base_path():
    page = requests.get(APP + "login", timeout=10).text
    assert f'<main data-prefix="{PREFIX}">' in page
    assert f"url('{PREFIX}/fonts/" in page


def test_a_prefix_header_of_the_client_does_not_reach_the_dashboard():
    page = requests.get(APP + "login", headers={"X-Forwarded-Prefix": "/elsewhere"}, timeout=10).text
    assert f'<main data-prefix="{PREFIX}">' in page
    assert "/elsewhere" not in page


def test_the_page_names_its_assets_below_the_base_path(api_below_base_path):
    page = api_below_base_path.get(APP, timeout=10)
    assert page.status_code == 200, page.status_code
    assert f'src="{PREFIX}/assets/' in page.text
    assert f'window.__HERMES_BASE_PATH__="{PREFIX}"' in page.text


def test_sign_in_opens_the_dashboard_below_the_base_path(signed_in_below_base_path):
    _, visit = signed_in_below_base_path
    assert own(visit["requested"], PROXY_URL), "the page made no request to its own server"
    assert not outside(visit["requested"]), f"requests left {PREFIX}: {outside(visit['requested'])}"
    assert below(visit["url"]), visit["url"]
    login = {url: status for url, status in visit["responses"].items() if urlparse(url).path == PREFIX + "/auth/password-login"}
    assert login and set(login.values()) == {200}, login
    api = {url: status for url, status in visit["responses"].items() if below(url, PREFIX + "/api")}
    assert any(status == 200 for status in api.values()), f"no API call below {PREFIX} succeeded: {api}"


def test_assets_load_below_the_base_path(signed_in_below_base_path):
    _, visit = signed_in_below_base_path
    assets = {url: status for url, status in visit["responses"].items() if below(url, PREFIX + "/assets")}
    assert any(urlparse(url).path.endswith(".js") for url in assets), f"no bundle was loaded below the base path: {visit['responses']}"
    assert any(urlparse(url).path.endswith(".css") for url in assets), f"no stylesheet was loaded below the base path: {visit['responses']}"
    files = {url: status for url, status in visit["responses"].items() if below(url) and not below(url, PREFIX + "/api")}
    failed = {url: status for url, status in files.items() if status >= 400}
    assert not failed, f"files failed: {failed}"


def test_document_names_no_url_outside_the_base_path(signed_in_below_base_path):
    context, _ = signed_in_below_base_path
    page = context.new_page()
    page.goto(APP)
    mounted(page)
    page.wait_for_load_state("networkidle")
    named = [url for url in page.evaluate(ROOT_ABSOLUTE_URLS) if not below(url)]
    page.close()
    assert not named, f"the page names URLs outside {PREFIX}: {named}"


def test_plugin_tab_adds_a_task_below_the_base_path(signed_in_below_base_path):
    context, _ = signed_in_below_base_path
    page = context.new_page()
    requested, responses = record(page)
    page.goto(APP + "todo")
    mounted(page)
    page.get_by_placeholder("Task title").fill("task below the base path")
    with page.expect_response(lambda response: urlparse(response.url).path == PREFIX + "/api/plugins/todo/add") as answer:
        page.get_by_role("button", name="Add", exact=True).click()
    assert answer.value.status == 200, answer.value.status
    page.get_by_text("task below the base path").first.wait_for(timeout=30000)
    page.wait_for_load_state("networkidle")
    # the dashboard serves a plugin below its profile: /dashboard-plugins/@default/todo/
    plugin = [url for url in responses if below(url, PREFIX + "/dashboard-plugins/@default/todo")]
    page.close()
    assert plugin, f"the TODO plugin was not loaded below {PREFIX}: {list(responses)}"
    assert not outside(requested), f"requests left {PREFIX}: {outside(requested)}"


def test_navigation_between_tabs_stays_below_the_base_path(signed_in_below_base_path):
    context, _ = signed_in_below_base_path
    page = context.new_page()
    requested, _ = record(page)
    page.goto(APP + "todo")
    mounted(page)
    page.get_by_role("link", name="Pairing").first.click()
    page.wait_for_url(lambda url: urlparse(url).path != PREFIX + "/todo", timeout=30000)
    page.wait_for_load_state("networkidle")
    target = urlparse(page.url).path
    assert below(page.url), f"the tab link left {PREFIX}: {page.url}"
    page.reload()
    mounted(page)
    page.wait_for_load_state("networkidle")
    path = urlparse(page.url).path
    page.close()
    assert path == target, f"the reload of {target} landed on {path}"
    assert not outside(requested), f"requests left {PREFIX}: {outside(requested)}"


def test_websocket_opens_below_the_base_path(signed_in_below_base_path):
    context, _ = signed_in_below_base_path
    page = context.new_page()
    requested, _ = record(page)
    page.goto(APP)
    mounted(page)
    state = page.evaluate("""async () => {
        const url = await window.__HERMES_PLUGIN_SDK__.buildWsUrl('/api/events', { channel: 'base-path-e2e' })
        return await new Promise(resolve => {
            const socket = new WebSocket(url)
            socket.onopen = () => { resolve(['open', socket.url]); socket.close() }
            socket.onerror = () => resolve(['error', socket.url])
        })
    }""")
    page.close()
    assert state[0] == "open", state
    assert below(state[1]), state
    sockets = [url for url in requested if urlparse(url).scheme in ("ws", "wss")]
    assert sockets and all(below(url) for url in sockets), sockets
