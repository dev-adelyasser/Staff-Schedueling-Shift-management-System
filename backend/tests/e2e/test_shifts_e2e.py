"""
backend/tests/e2e/test_shifts_e2e.py
──────────────────────────────────────
E2E tests for the Shift Scheduling slice — Playwright + Page Object Model.

IMPORTANT: These tests require a running application (backend + frontend).
Run with:  pytest backend/tests/e2e/ --headed (to observe) or headless.

All selectors use data-testid attributes only (never CSS class / XPath).
Page Object classes live in backend/tests/e2e/pages/shift_page.py.

NOTE: Gherkin scenarios (.feature files) must be written from the actual
use-case specification documents — AI does not generate scenario text.
"""

import pytest

pytestmark = pytest.mark.e2e


class ShiftPage:
    """Page Object for the Shift Scheduling UI."""

    def __init__(self, page):
        self._page = page

    def navigate(self):
        self._page.goto("/shifts")

    def fill_create_form(self, *, title, start_time, end_time, department_id, headcount=1):
        self._page.get_by_test_id("shift-title-input").fill(title)
        self._page.get_by_test_id("shift-start-input").fill(start_time)
        self._page.get_by_test_id("shift-end-input").fill(end_time)
        self._page.get_by_test_id("shift-department-input").fill(str(department_id))
        self._page.get_by_test_id("shift-headcount-input").fill(str(headcount))

    def submit(self):
        self._page.get_by_test_id("shift-submit-btn").click()

    def get_success_message(self):
        return self._page.get_by_test_id("shift-success-toast").text_content()

    def get_validation_error(self):
        return self._page.get_by_test_id("shift-error-message").text_content()


@pytest.fixture()
def shift_page(page):
    return ShiftPage(page)


# ── Smoke tests (require running app) ─────────────────────────────────────── #

@pytest.mark.skip(reason="Requires running frontend — wire after UI is built")
def test_create_shift_happy_path_e2e(shift_page):
    """UC-02: Admin can create a shift and receives a success confirmation."""
    shift_page.navigate()
    shift_page.fill_create_form(
        title="Morning Shift",
        start_time="2026-07-01T08:00",
        end_time="2026-07-01T16:00",
        department_id=1,
        headcount=2,
    )
    shift_page.submit()
    msg = shift_page.get_success_message()
    assert "Morning Shift" in msg


@pytest.mark.skip(reason="Requires running frontend — wire after UI is built")
def test_create_shift_end_before_start_shows_error(shift_page):
    """HR-05: submitting end < start shows a validation error in the UI."""
    shift_page.navigate()
    shift_page.fill_create_form(
        title="Bad Shift",
        start_time="2026-07-01T16:00",
        end_time="2026-07-01T08:00",  # invalid
        department_id=1,
    )
    shift_page.submit()
    err = shift_page.get_validation_error()
    assert err is not None and len(err) > 0
