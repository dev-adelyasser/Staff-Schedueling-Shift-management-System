"""
backend/tests/e2e/conftest.py
──────────────────────────────
Playwright fixtures for Person 2's E2E tests.

All E2E tests use data-testid selectors only (never CSS class or positional).
Page Objects live in backend/tests/e2e/pages/.
"""

import os
import pytest
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def browser_context_args():
    return {"base_url": BASE_URL}


@pytest.fixture()
def page(browser: Browser):
    context = browser.new_context(base_url=BASE_URL)
    p = context.new_page()
    yield p
    context.close()
