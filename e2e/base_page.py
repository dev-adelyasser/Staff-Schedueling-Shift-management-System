"""
e2e/base_page.py
─────────────────
Playwright Page Object Model (POM) – Base class.

Architecture
────────────
All E2E page objects MUST inherit from BasePage.
This provides:
  • Consistent selector strategy (data-testid first).
  • Built-in wait helpers that prevent flaky tests.
  • Gherkin step hooks so feature files map cleanly to methods.
  • Screenshot on failure (captured in CI artifacts).

Gherkin mapping convention
───────────────────────────
  Given "I am on the login page"    → LoginPage.navigate()
  When  "I enter valid credentials" → LoginPage.fill_credentials(email, pwd)
  Then  "I see the dashboard"       → DashboardPage.assert_visible()

Usage:
    from e2e.pages.login_page import LoginPage

    async def test_login(page):
        login = LoginPage(page, base_url="http://localhost:3000")
        await login.navigate()
        await login.fill_credentials("admin@example.com", "Admin@12345")
        await login.submit()
        await login.assert_redirected_to("/dashboard")
"""

from __future__ import annotations

import asyncio
from typing import Any
from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeout


class BasePage:
    """
    Abstract base for all Page Object Models.

    Every concrete page class:
      1. Inherits BasePage.
      2. Declares a PATH class variable (relative URL).
      3. Implements assert_loaded() to verify the page rendered correctly.
    """

    PATH: str = "/"  # Override in subclasses

    # ── Default timeouts (ms) ──────────────────────────────────
    DEFAULT_TIMEOUT:      int = 10_000   # element wait
    NAVIGATION_TIMEOUT:   int = 30_000   # full page load
    ANIMATION_TIMEOUT:    int = 500      # wait for CSS transitions

    def __init__(self, page: Page, base_url: str = "http://localhost:3000") -> None:
        self._page     = page
        self._base_url = base_url.rstrip("/")

    # ── Navigation ────────────────────────────────────────────

    async def navigate(self, path: str | None = None) -> None:
        """
        Navigate to this page (or a given sub-path).
        Gherkin: Given "I am on the <page> page"
        """
        url = f"{self._base_url}/{(path or self.PATH).lstrip('/')}"
        await self._page.goto(url, wait_until="networkidle",
                              timeout=self.NAVIGATION_TIMEOUT)
        await self.assert_loaded()

    async def assert_loaded(self) -> None:
        """
        Override to assert page-specific markers are visible.
        Gherkin: Then "the page has loaded"
        """
        pass  # pragma: no cover

    async def assert_redirected_to(self, expected_path: str) -> None:
        """
        Gherkin: Then "I am redirected to <path>"
        """
        await self._page.wait_for_url(
            f"**{expected_path}",
            timeout=self.NAVIGATION_TIMEOUT,
        )

    # ── Element helpers ───────────────────────────────────────

    def by_test_id(self, test_id: str) -> Locator:
        """Primary selector strategy: data-testid attribute."""
        return self._page.get_by_test_id(test_id)

    def by_role(self, role: str, *, name: str | None = None) -> Locator:
        """Semantic role selector (accessible)."""
        kwargs: dict[str, Any] = {}
        if name:
            kwargs["name"] = name
        return self._page.get_by_role(role, **kwargs)  # type: ignore[arg-type]

    def by_label(self, label: str) -> Locator:
        return self._page.get_by_label(label)

    def by_text(self, text: str) -> Locator:
        return self._page.get_by_text(text)

    # ── Interaction helpers ───────────────────────────────────

    async def click(self, locator: Locator) -> None:
        await locator.wait_for(state="visible", timeout=self.DEFAULT_TIMEOUT)
        await locator.click()

    async def fill(self, locator: Locator, value: str) -> None:
        await locator.wait_for(state="visible", timeout=self.DEFAULT_TIMEOUT)
        await locator.fill(value)

    async def select_option(self, locator: Locator, value: str) -> None:
        await locator.wait_for(state="visible", timeout=self.DEFAULT_TIMEOUT)
        await locator.select_option(value)

    # ── Assertion helpers ─────────────────────────────────────

    async def assert_visible(self, locator: Locator) -> None:
        """Gherkin: Then "I see <element>"."""
        await locator.wait_for(state="visible", timeout=self.DEFAULT_TIMEOUT)

    async def assert_text_contains(self, locator: Locator, expected: str) -> None:
        """Gherkin: Then "<element> contains '<text>'"."""
        await locator.wait_for(state="visible", timeout=self.DEFAULT_TIMEOUT)
        text = await locator.inner_text()
        assert expected in text, f"Expected '{expected}' in '{text}'"

    async def assert_url_contains(self, fragment: str) -> None:
        assert fragment in self._page.url, (
            f"Expected URL to contain '{fragment}', got '{self._page.url}'"
        )

    async def assert_toast(self, message: str) -> None:
        """
        Wait for a toast/snackbar notification.
        Gherkin: Then "I see a success message '<message>'"
        """
        toast = self._page.get_by_role("alert")
        await self.assert_text_contains(toast, message)

    # ── Diagnostic helpers ────────────────────────────────────

    async def screenshot(self, name: str = "screenshot") -> None:
        """Save a debug screenshot (called automatically on failure via conftest)."""
        await self._page.screenshot(path=f"e2e/screenshots/{name}.png", full_page=True)

    async def wait_for_network_idle(self) -> None:
        await self._page.wait_for_load_state("networkidle",
                                             timeout=self.NAVIGATION_TIMEOUT)

    async def wait_for_animation(self) -> None:
        """Give CSS animations time to settle."""
        await asyncio.sleep(self.ANIMATION_TIMEOUT / 1000)

    # ── API bridge (for test setup, not user journeys) ────────

    async def api_post(self, path: str, payload: dict) -> dict:
        """
        Make an API call from within Playwright context.
        Used for data seeding without going through the UI.
        """
        api_url = f"http://localhost:8000/api/v1{path}"
        response = await self._page.request.post(
            api_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        return await response.json()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} url={self._page.url!r}>"
