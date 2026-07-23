"""End-to-end tests for the ``@check.check_func`` step-function path (issue #3).

These mirror real-world usage where a *step function* is decorated with
``@check.check_func`` (pytest-check) so that its ``assert`` becomes a soft check:
the ``AssertionError`` is swallowed and logged instead of raised. The step is
then called from a test linked to a Jira issue via ``@bug``.

Unlike the rest of the suite (pure in-process unit tests), these run a real
pytest sub-session so we can assert the *actual* reported outcome. We use
``runpytest_subprocess`` on purpose: the outer session already loads
soft-assertion plugins (pytest-check / pytest-playwright) and running the nested
session in-process would nest their soft-assertion scopes -- which pytest-check
forbids. A separate process gives one clean scope and a genuine end-to-end check.

Jira is stubbed in the nested conftest (``_check_if_issue_open``) so no network
access is required.
"""

import os
from pathlib import Path

import pytest

pytest.importorskip("pytest_check")


@pytest.fixture(autouse=True)
def _ensure_package_importable(monkeypatch):
    """Make ``pytest_jira_xfail`` importable inside the subprocess even when the
    package is only on the source path (not pip-installed), e.g. locally."""
    import pytest_jira_xfail

    root = str(Path(pytest_jira_xfail.__file__).resolve().parent.parent)
    existing = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv(
        "PYTHONPATH", root + (os.pathsep + existing if existing else "")
    )


def _conftest(open_keys):
    """A conftest that registers the plugin on collection with Jira stubbed."""
    return f"""
import pytest
from pytest_jira_xfail.jira_helper import PytestJiraHelper

OPEN_KEYS = {set(open_keys)!r}


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    # ``__wrapped__`` bypasses the @singleton so each session gets a fresh helper.
    jira = PytestJiraHelper.__wrapped__("http://jira.test", "user", "token")
    jira._check_if_issue_open = lambda key: key in OPEN_KEYS
    jira.process_linked_jira_issues(items)
"""


# A @check.check_func step function whose assert becomes a soft check, plus the
# @bug import -- prepended to every generated test module.
_PREAMBLE = """
import pytest_check as check
from pytest_jira_xfail.annotations import bug


@check.check_func
def then_values_are_equal(actual, expected):
    assert actual == expected, f"{actual} != {expected}"
"""


def _run(pytester, open_keys, body):
    pytester.makeconftest(_conftest(open_keys))
    pytester.makepyfile(_PREAMBLE + body)
    # Disable pytest-playwright in the nested session: it wraps every test in its
    # own soft-assertion scope, which would nest with pytest-check's scope.
    return pytester.runpytest_subprocess("-p", "no:playwright")


def test_open_bug_soft_check_failure_is_xfail(pytester):
    result = _run(
        pytester,
        open_keys={"AP-1"},
        body="""
@bug("AP-1")
def test_step_soft_fails():
    then_values_are_equal(1, 2)
""",
    )
    result.assert_outcomes(xfailed=1)


def test_resolved_bug_soft_check_failure_is_a_real_failure(pytester):
    result = _run(
        pytester,
        open_keys=set(),  # AP-1 is resolved -> no xfail marker injected
        body="""
@bug("AP-1")
def test_step_soft_fails():
    then_values_are_equal(1, 2)
""",
    )
    result.assert_outcomes(failed=1)


def test_open_bug_multiple_check_func_steps_is_xfail(pytester):
    # Mirrors a realistic test that calls several @check.check_func steps in a
    # row; a soft failure in any of them must still be a single deterministic
    # XFAIL while the bug is open.
    result = _run(
        pytester,
        open_keys={"AP-1"},
        body="""
@bug("AP-1")
def test_multiple_steps():
    then_values_are_equal(1, 1)
    then_values_are_equal("expected", "actual")  # soft-fails here
    then_values_are_equal(3, 3)
""",
    )
    result.assert_outcomes(xfailed=1)


def test_open_bug_all_steps_pass_is_xpass(pytester):
    # Bug is (apparently) fixed: all soft checks pass, so the still-linked test
    # surfaces as XPASS, prompting the team to remove the @bug marker.
    result = _run(
        pytester,
        open_keys={"AP-1"},
        body="""
@bug("AP-1")
def test_all_steps_pass():
    then_values_are_equal(1, 1)
    then_values_are_equal("same", "same")
""",
    )
    result.assert_outcomes(xpassed=1)
