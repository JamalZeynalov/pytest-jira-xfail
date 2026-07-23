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


# --------------------------------------------------------------------------- #
# Realistic step-function shape: @check.check_func stacked on top of another   #
# step decorator, wrapping a function with several asserts (mirrors real usage)#
# --------------------------------------------------------------------------- #

# A @check.check_func-decorated BDD-style step, stacked on a second decorator,
# with multiple asserts and an allure attachment on failure -- structurally the
# same as the reported side-project step function.
_STEP_MODULE = '''
import functools

import allure
import pytest_check as check


def decor_then(text):
    """Stand-in for a BDD 'then' step decorator (wraps + forwards)."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with allure.step(text):
                return fn(*args, **kwargs)
        return wrapper
    return deco


@check.check_func
@decor_then("bottleneck bucket is identical between both services")
def then_bottleneck_matches(cs_response, lc_response):
    cs_bucket = cs_response.get("bottleneck") or []
    lc_bucket = lc_response.get("bottleneck") or []
    assert cs_bucket, "CS 'bottleneck' is empty - cannot verify parity"
    assert lc_bucket, "LC 'bottleneck' is empty - cannot verify parity"
    diff = [
        (a, b) for a, b in zip(cs_bucket, lc_bucket) if a != b
    ]
    if diff:
        allure.attach(str(diff), "cross_service_bottleneck_diff")
    assert not diff, f"clusterSuggestions 'bottleneck' differs: {diff}"
'''


def test_check_func_step_function_open_issue_is_xfailed(jira_pytester):
    jira_pytester.makepyfile(steps=_STEP_MODULE)
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug
        from steps import then_bottleneck_matches

        @bug("OPEN-1")
        def test_cross_service_parity():
            cs = {"bottleneck": [{"id": 1, "v": 10}]}
            lc = {"bottleneck": [{"id": 1, "v": 99}]}  # differs -> soft failure
            then_bottleneck_matches(cs, lc)
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)


def test_check_func_step_function_resolved_issue_fails(jira_pytester):
    jira_pytester.makepyfile(steps=_STEP_MODULE)
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug
        from steps import then_bottleneck_matches

        @bug("DONE-1")
        def test_cross_service_parity():
            cs = {"bottleneck": [{"id": 1, "v": 10}]}
            lc = {"bottleneck": [{"id": 1, "v": 99}]}
            then_bottleneck_matches(cs, lc)
        """
    )
    jira_pytester.runpytest().assert_outcomes(failed=1)


def test_check_func_step_function_passing_is_xpassed(jira_pytester):
    jira_pytester.makepyfile(steps=_STEP_MODULE)
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug
        from steps import then_bottleneck_matches

        @bug("OPEN-1")
        def test_cross_service_parity():
            cs = {"bottleneck": [{"id": 1, "v": 10}]}
            lc = {"bottleneck": [{"id": 1, "v": 10}]}  # identical -> passes
            then_bottleneck_matches(cs, lc)
        """
    )
    jira_pytester.runpytest().assert_outcomes(xpassed=1)


def test_multiple_check_func_steps_open_issue_is_xfailed(jira_pytester):
    # Several soft failures collected across multiple step calls in one test.
    jira_pytester.makepyfile(steps=_STEP_MODULE)
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug
        from steps import then_bottleneck_matches

        @bug("OPEN-1")
        def test_cross_service_parity():
            cs = {"bottleneck": [{"id": 1, "v": 10}]}
            lc = {"bottleneck": [{"id": 1, "v": 99}]}
            then_bottleneck_matches(cs, lc)   # soft failure #1
            then_bottleneck_matches({}, lc)   # soft failure #2 (CS empty)
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)
