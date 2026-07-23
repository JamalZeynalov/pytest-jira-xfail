"""Runtime refiner that enforces the ``@bug`` expectations on the injected xfail.

The plugin injects a plain ``pytest.mark.xfail(reason=..., run=...)`` on tests
linked to open Jira issues -- deliberately *without* a ``raises=`` argument (see
issue #3: ``raises=`` makes pytest-check classify soft-assertion failures by
string-matching the rendered traceback, which is environment/xdist-dependent).

Because there is no ``raises=`` on the marker, pytest turns *any* raised error
into an xfail. This runtime hook re-checks the real exception against the
expected type(s) -- and any ``error_contains`` substrings -- using genuine
``isinstance`` / substring checks, and cancels the xfail when nothing matches so
the test is reported as a real failure.

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
when the raised error is unexpected. pytest-core ``skipping`` then produces a
genuine ``failed`` report, and every downstream reporter reads the correct
status. The console outcome and all report backends stay in agreement.

For soft-assertion failures (e.g. pytest-check) there is no exception during the
``call`` phase at this point (``call.excinfo`` is ``None``), so the xfail is left
untouched -- giving a deterministic XFAIL in every environment.
"""

import pytest
from _pytest.skipping import xfailed_key

_PLUGIN_NAME = "pytest_jira_xfail_error_contains"

# Attribute set on an item (during collection) holding the list of
# (exception_type, substrings_or_None, case_sensitive) matchers derived from its
# @bug markers.
MATCHERS_ATTR = "_jira_xfail_matchers"


class _ErrorContainsPlugin:
    """Cancels the injected ``xfail`` when the raised error is not the one the
    open bug is expected to produce (wrong type, or message missing every
    ``error_contains`` substring)."""

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        # ``tryfirst`` makes this the outermost wrapper. The code *before* the
        # yield therefore runs first -- ahead of pytest-core skipping evaluating
        # the xfail and ahead of any reporter reading the final status.
        _veto_xfail_if_error_unexpected(item, call)
        return (yield)


def _veto_xfail_if_error_unexpected(item, call):
    """Clear the ``xfailed`` stash entry when the call-phase error does not match
    any expected type / message, so pytest reports it as a real failure.

    A no-op when there is no call-phase exception, no matchers, or the test was
    not going to be xfailed anyway.
    """
    # No exception during the call phase (the test passed, was not run, or failed
    # via a soft-assertion library that swallows the exception): leave the native
    # xfail decision untouched.
    if call.when != "call" or call.excinfo is None:
        return

    matchers = getattr(item, MATCHERS_ATTR, None)
    if not matchers:
        return

    # Only act on tests that pytest is about to xfail. Anything else is left as is.
    if not item.stash.get(xfailed_key, None):
        return

    error = call.excinfo.value
    message = str(error)
    for exc_type, substrings, case_sensitive in matchers:
        if isinstance(error, exc_type) and (
            substrings is None or _message_contains(message, substrings, case_sensitive)
        ):
            # The raised error matches an open bug -> keep it as XFAIL.
            return

    # The raised error does not match any expected type (or its message does not
    # contain the expected substrings) -> this is a different problem. Cancel the
    # xfail so pytest-core skipping reports a genuine failure.
    item.stash[xfailed_key] = None


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
