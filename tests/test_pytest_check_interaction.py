"""Regression tests for the interaction with pytest-check (issue #3).

pytest-check turns assertion failures into *soft* failures: the ``AssertionError``
is swallowed during the ``call`` phase and only logged. Previously the plugin put
``raises=AssertionError`` on the injected xfail marker, which made pytest-check
decide xfail-vs-fail by string-matching the rendered traceback for the token
``"AssertionError"`` -- an environment/xdist-dependent check that produced FAILED
in some setups and XFAILED in others.

The plugin no longer passes ``raises=`` (the expected type is enforced by our own
runtime refiner), so soft-check failures are deterministically XFAILED when the
linked issue is open.
"""

import pytest

# pytest-check is an optional, test-only dependency.
pytest.importorskip("pytest_check")


def test_soft_check_failure_with_open_issue_is_xfailed(jira_pytester):
    jira_pytester.makepyfile(
        """
        import pytest_check as check
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1")
        def test_it():
            check.equal(1, 2, "one is not two")
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)


def test_soft_check_failure_with_resolved_issue_fails(jira_pytester):
    # Control: with a resolved issue no xfail is injected, so a soft-check
    # failure is a real failure, exactly as pytest-check would report it.
    jira_pytester.makepyfile(
        """
        import pytest_check as check
        from pytest_jira_xfail.annotations import bug

        @bug("DONE-1")
        def test_it():
            check.equal(1, 2, "one is not two")
        """
    )
    jira_pytester.runpytest().assert_outcomes(failed=1)


def test_soft_check_passing_with_open_issue_is_xpassed(jira_pytester):
    jira_pytester.makepyfile(
        """
        import pytest_check as check
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1")
        def test_it():
            check.equal(1, 1, "always equal")
        """
    )
    jira_pytester.runpytest().assert_outcomes(xpassed=1)


def test_soft_check_via_check_func_with_open_issue_is_xfailed(jira_pytester):
    # The exact reproduction from issue #3: a bare assert (no "AssertionError"
    # token in the message) inside a @check.check_func-decorated helper.
    jira_pytester.makepyfile(
        """
        import pytest_check as check
        from pytest_jira_xfail.annotations import bug

        @check.check_func
        def _both_equal(a, b):
            assert a == b, f"{a} != {b}"

        @bug("OPEN-123")
        def test_it():
            _both_equal(1, 2)
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)
