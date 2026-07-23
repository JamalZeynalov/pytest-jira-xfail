"""Runtime helpers that refine the native ``xfail`` behaviour of the plugin.

pytest's built-in ``xfail(raises=...)`` matches on the *type* of the raised
exception only. To support the ``@bug(..., error_contains=...)`` option we need
to additionally inspect the raised exception *message* at run time and, when it
does not contain any of the expected substrings, report the test as a real
failure instead of an expected one.
"""

import pytest

_PLUGIN_NAME = "pytest_jira_xfail_error_contains"

# Attribute set on an item (during collection) holding the list of
# (exception_type, substrings_or_None) matchers derived from its open @bug marks.
MATCHERS_ATTR = "_jira_xfail_matchers"


class _ErrorContainsPlugin:
    """Downgrades an ``xfail`` back to a failure when the error message
    does not contain any of the expected substrings."""

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        # ``tryfirst`` makes this the outermost wrapper, so the code below runs
        # after pytest's own skipping plugin has already decided about xfail.
        report = yield

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

        # The error type may match, but its message does not contain any of the
        # expected substrings -> this is a different problem, report it as a
        # genuine failure so it is not silently hidden.
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
