"""
e2e/conftest.py
────────────────
Playwright configuration for E2E tests.

Provides:
  • `browser` fixture (Chromium, headless by default).
  • `page` fixture with auto-screenshot on failure.
  • `base_url` from environment (default: http://localhost:3000).

Run:
  pytest e2e/ --headed          # visible browser
  pytest e2e/ --browser=firefox # switch engine
"""

import os
import pytest
from playwright.async_api import async_playwright, Browser, Page


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.getenv("E2E_BASE_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
async def browser():
    async with async_playwright() as pw:
        b: Browser = await pw.chromium.launch(
            headless=os.getenv("E2E_HEADLESS", "true").lower() == "true"
        )
        yield b
        await b.close()


@pytest.fixture()
async def page(browser: Browser, request) -> Page:
    """
    Per-test page with automatic screenshot on failure.
    Screenshots saved to e2e/screenshots/<test_name>.png.
    """
    ctx  = await browser.new_context()
    pg   = await ctx.new_page()
    yield pg

    if request.node.rep_call.failed if hasattr(request.node, "rep_call") else False:
        os.makedirs("e2e/screenshots", exist_ok=True)
        name = request.node.nodeid.replace("/", "_").replace("::", "_")
        await pg.screenshot(path=f"e2e/screenshots/{name}.png", full_page=True)

    await ctx.close()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach test result to the request node for screenshot-on-failure."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)
