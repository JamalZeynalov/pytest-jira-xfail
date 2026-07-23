"""Runtime refiner that enforces the ``@bug`` expectations on the injected xfail.

The plugin injects a plain ``pytest.mark.xfail(reason=..., run=...)`` on tests
linked to open Jira issues -- deliberately *without* a ``raises=`` argument (see
issue #3: ``raises=`` makes pytest-check classify soft-assertion failures by
string-matching the rendered traceback, which is environment/xdist-dependent).

Because there is no ``raises=`` on the marker, pytest turns *any* raised error
into an xfail. This runtime hook re-checks the real failure against the expected
type(s) -- and any ``error_contains`` substrings -- and cancels the xfail when
nothing matches so the test is reported as a real failure.

Why we *cancel the xfail up front* instead of downgrading the finished report
--------------------------------------------------------------------------------
``pytest_runtest_makereport`` is a wrapped hook. pytest-core's ``skipping``
plugin turns the report into an xfail in its *post-yield*, and reporters such as
allure read the final status in *their* post-yield. Mutating ``report.outcome``
from an outermost (``tryfirst``) wrapper happens *after* those reporters have
already recorded the status, so the console would say FAILED while allure (and
Allure TestOps) still showed the test as skipped/xfailed.

Instead we run in the *pre-yield* phase of the outermost wrapper -- before any
plugin evaluates or reads the xfail -- and clear pytest's ``xfailed`` stash entry
when the failure is unexpected. pytest-core ``skipping`` then produces a genuine
``failed`` report, and every downstream reporter reads the correct status.

Hard vs soft failures
--------------------------------------------------------------------------------
* Hard (call-phase) exceptions are matched by real ``isinstance`` + substring
  checks against ``call.excinfo``.
* Soft-assertion failures (pytest-check) do not raise during the ``call`` phase
  (``call.excinfo`` is ``None`` here). We instead read pytest-check's collected
  failure messages (still present at pre-yield -- pytest-check clears them in its
  own post-yield) and enforce the ``error_contains`` substrings against them:
  the xfail is kept only when *every* soft failure matches an expected substring.
  Type-only ``@bug`` markers (no ``error_contains``) keep the deterministic XFAIL
  for any soft assertion, exactly as before. We match user-provided substrings
  against the failure *message* (stable across environments), never the exception
  type token -- so this does not reintroduce the issue #3 non-determinism.
"""

import pytest
from _pytest.skipping import xfailed_key

_PLUGIN_NAME = "pytest_jira_xfail_error_contains"

# Attribute set on an item (during collection) holding the list of
# (exception_type, substrings_or_None, case_sensitive) matchers derived from its
# @bug markers.
MATCHERS_ATTR = "_jira_xfail_matchers"


class _ErrorContainsPlugin:
    """Cancels the injected ``xfail`` when the failure is not the one the open bug
    is expected to produce (wrong type, or message missing every ``error_contains``
    substring), for both hard exceptions and pytest-check soft assertions."""

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        # ``tryfirst`` makes this the outermost wrapper. The code *before* the
        # yield therefore runs first -- ahead of pytest-core skipping evaluating
        # the xfail and ahead of any reporter reading the final status.
        _veto_xfail_if_error_unexpected(item, call)
        return (yield)


def _veto_xfail_if_error_unexpected(item, call):
    """Clear the ``xfailed`` stash entry when the call-phase failure does not match
    any expected type / message, so pytest reports it as a real failure.

    A no-op when there is no failure, no matchers, or the test was not going to be
    xfailed anyway.
    """
    if call.when != "call":
        return

    matchers = getattr(item, MATCHERS_ATTR, None)
    if not matchers:
        return

    # Only act on tests that pytest is about to xfail. Anything else is left as is.
    if not item.stash.get(xfailed_key, None):
        return

    if call.excinfo is not None:
        # Hard call-phase exception: match the real exception object.
        if not _hard_error_is_expected(call.excinfo.value, matchers):
            item.stash[xfailed_key] = None
        return

    # No hard exception: the test either passed (-> XPASS, leave it) or failed via
    # a soft-assertion library. Enforce ``error_contains`` on any soft failures.
    soft_failures = _collect_soft_failures()
    if soft_failures and not _soft_failures_all_expected(soft_failures, matchers):
        item.stash[xfailed_key] = None


def _hard_error_is_expected(error, matchers):
    """True if a raised exception matches an expected type (and substring)."""
    message = str(error)
    for exc_type, substrings, case_sensitive in matchers:
        if isinstance(error, exc_type) and (
            substrings is None or _message_contains(message, substrings, case_sensitive)
        ):
            return True
    return False


def _soft_failures_all_expected(failures, matchers):
    """True if *every* soft-assertion failure message is expected by some matcher.

    A single unexpected soft failure means a different problem is present, so the
    whole test must surface as a real failure rather than a hidden XFAIL.
    """
    return all(
        any(_matcher_accepts_soft(matcher, message) for matcher in matchers)
        for message in failures
    )


def _matcher_accepts_soft(matcher, message):
    """Whether a matcher accepts a soft-assertion failure message.

    Soft failures are ``AssertionError`` based, so a matcher only applies when its
    expected type is (a base of) ``AssertionError``. A type-only matcher accepts
    any soft assertion; otherwise the message must contain an expected substring.
    """
    exc_type, substrings, case_sensitive = matcher
    if not issubclass(AssertionError, exc_type):
        return False
    if substrings is None:
        return True
    return _message_contains(message, substrings, case_sensitive)


def _collect_soft_failures():
    """Return pytest-check's collected failure messages, or [] when unavailable.

    Read at makereport pre-yield, before pytest-check clears them in its own
    post-yield. Safe no-op when pytest-check is not installed.
    """
    try:
        from pytest_check import check_log

        failures = check_log.get_failures()
    except Exception:
        return []
    return list(failures) if failures else []


def _message_contains(message, substrings, case_sensitive):
    """Return True if the message contains at least one of the substrings."""
    if not case_sensitive:
        message = message.lower()
        substrings = [sub.lower() for sub in substrings]
    return any(sub in message for sub in substrings)


def register_error_contains_plugin(config):
    """Register the runtime plugin once per pytest session."""
    plugin_manager = config.pluginmanager
    if not plugin_manager.has_plugin(_PLUGIN_NAME):
        plugin_manager.register(_ErrorContainsPlugin(), _PLUGIN_NAME)
