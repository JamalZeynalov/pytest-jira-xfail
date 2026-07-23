"""Runtime refiner that enforces the ``@bug`` expectations on the injected xfail.

The plugin injects a plain ``pytest.mark.xfail(reason=..., run=...)`` on tests
linked to open Jira issues -- deliberately *without* a ``raises=`` argument (see
issue #3: ``raises=`` makes pytest-check classify soft-assertion failures by
string-matching the rendered traceback, which is environment/xdist-dependent).

Because there is no ``raises=`` on the marker, pytest turns *any* raised error
into an xfail. This runtime hook re-checks the real exception against the
expected type(s) -- and any ``error_contains`` substrings -- using genuine
``isinstance`` / substring checks, and downgrades the report back to a real
failure when nothing matches.

For soft-assertion failures (e.g. pytest-check) there is no exception during the
``call`` phase, so ``call.excinfo`` is ``None`` and the report is left exactly as
whichever plugin produced it -- giving deterministic XFAIL in every environment.
"""

import pytest

_PLUGIN_NAME = "pytest_jira_xfail_error_contains"

# Attribute set on an item (during collection) holding the list of
# (exception_type, substrings_or_None, case_sensitive) matchers derived from its
# @bug markers.
MATCHERS_ATTR = "_jira_xfail_matchers"


class _ErrorContainsPlugin:
    """Downgrades an ``xfail`` back to a failure when the raised error does not
    match any expected type (and, when given, any expected message substring)."""

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        # ``tryfirst`` makes this the outermost wrapper, so the code below runs
        # after pytest's own skipping plugin has already decided about xfail.
        report = yield

        # No exception during the call phase (e.g. the test passed, was not run,
        # or failed via a soft-assertion library that swallows the exception):
        # leave the report untouched so the native xfail decision stands.
        if call.when != "call" or call.excinfo is None:
            return report

        matchers = getattr(item, MATCHERS_ATTR, None)
        if not matchers:
            return report

        # Only refine reports that were turned into an xfail because of the
        # raised error. Anything else (real failure, xpass, NOTRUN) is left as is.
        if getattr(report, "wasxfail", None) is None:
            return report

        error = call.excinfo.value
        message = str(error)
        for exc_type, substrings, case_sensitive in matchers:
            if not isinstance(error, exc_type):
                continue
            if substrings is None or _message_contains(
                message, substrings, case_sensitive
            ):
                # The raised error matches an open bug -> keep it as XFAIL.
                return report

        # The raised error does not match any expected type (or its message does
        # not contain the expected substrings) -> this is a different problem,
        # report it as a genuine failure so it is not silently hidden.
        report.outcome = "failed"
        if hasattr(report, "wasxfail"):
            del report.wasxfail
        return report


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
