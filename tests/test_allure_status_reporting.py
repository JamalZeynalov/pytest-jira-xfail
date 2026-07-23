"""Regression test: the Allure status must agree with the pytest outcome.

Reproduces the reported bug where a parametrized test using ``error_contains``
had one case that raised a *non-matching* message. pytest correctly reported it
as FAILED, but Allure (and Allure TestOps) still showed it as *skipped* (XFAIL).

Root cause: the old refiner mutated ``report.outcome`` from an outermost
(``tryfirst``) makereport wrapper, i.e. *after* reporters like allure had already
read the status in their own post-yield. The fix cancels the xfail up front (in
the pre-yield phase) so every reporter observes the correct final status.

A pure ``assert_outcomes`` test would NOT catch this -- the console outcome was
already correct. We must inspect what a reporter actually recorded, hence we run
a real sub-session with allure enabled and parse its results.
"""

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("allure_pytest")


_CONFTEST = """
import pytest
from pytest_jira_xfail.jira_helper import PytestJiraHelper


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    jira = PytestJiraHelper.__wrapped__("http://jira.test", "user", "token")
    jira._check_if_issue_open = lambda key: True  # AP-24202 is open
    jira.process_linked_jira_issues(items)
"""

# The exact user scenario: one parametrization matches an ``error_contains``
# substring (-> XFAIL), the other does not (-> real FAILURE).
_TEST = """
import allure
import pytest
from pytest_jira_xfail.annotations import bug


@allure.id("1")
@bug("AP-24202", error_contains=["buildingCeilingHeight", "buildingClearHeightIn"])
@pytest.mark.parametrize("msg", ["no buildingCeilingHeight", "nothing to raise"])
def test_plugin(msg):
    raise AssertionError(msg)
"""


@pytest.fixture(autouse=True)
def _ensure_package_importable(monkeypatch):
    import pytest_jira_xfail

    root = str(Path(pytest_jira_xfail.__file__).resolve().parent.parent)
    existing = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv(
        "PYTHONPATH", root + (os.pathsep + existing if existing else "")
    )


def _allure_statuses(pytester, test_body):
    pytester.makeconftest(_CONFTEST)
    pytester.makepyfile(test_body)

    # Subprocess for a clean, single soft-assertion scope; allure enabled.
    pytester.runpytest_subprocess(
        "-p", "no:playwright", "--alluredir=allure-results"
    )

    statuses = {}
    for result_file in (pytester.path / "allure-results").glob("*-result.json"):
        data = json.loads(result_file.read_text())
        statuses[data["name"]] = data["status"]
    return statuses


def test_allure_status_matches_pytest_outcome_for_error_contains(pytester):
    statuses = _allure_statuses(pytester, _TEST)

    assert statuses == {
        # message contains "buildingCeilingHeight" -> expected bug -> XFAIL
        "test_plugin[no buildingCeilingHeight]": "skipped",
        # message contains neither substring -> different problem -> real failure
        "test_plugin[nothing to raise]": "failed",
    }


def test_allure_status_is_passed_for_xpass(pytester):
    # A test linked to an open bug that unexpectedly passes is an XPASS. Allure
    # records XPASS as status "passed" (with an XPASS message), so it must not be
    # reported as skipped/failed.
    statuses = _allure_statuses(
        pytester,
        """
from pytest_jira_xfail.annotations import bug


@bug("AP-24202")
def test_unexpectedly_passes():
    assert True
""",
    )

    assert statuses == {"test_unexpectedly_passes": "passed"}
