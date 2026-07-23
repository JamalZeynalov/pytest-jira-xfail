"""Unit tests for the runtime refiner ``_refine_report``.

The refiner decides whether an injected xfail stays an XFAIL or is downgraded
back to a real FAILURE based on the exception actually raised. We test the pure
decision function directly with plain namespaces instead of a live pytest run.
"""

from types import SimpleNamespace

from pytest_jira_xfail.xfail_plugin import MATCHERS_ATTR, _refine_report


def _item(matchers=None):
    item = SimpleNamespace()
    if matchers is not None:
        setattr(item, MATCHERS_ATTR, matchers)
    return item


def _call(exc=None, when="call"):
    excinfo = SimpleNamespace(value=exc) if exc is not None else None
    return SimpleNamespace(when=when, excinfo=excinfo)


def _xfail_report():
    return SimpleNamespace(outcome="skipped", wasxfail="open bug AP-1")


# --------------------------------------------------------------------------- #
# No-op cases: report is left exactly as produced upstream                     #
# --------------------------------------------------------------------------- #


def test_no_exception_leaves_report_untouched():
    report = _xfail_report()
    _refine_report(_item([(IndexError, None, True)]), _call(exc=None), report)

    assert report.outcome == "skipped"
    assert report.wasxfail == "open bug AP-1"


def test_non_call_phase_left_untouched():
    report = _xfail_report()
    _refine_report(
        _item([(IndexError, None, True)]),
        _call(exc=IndexError("x"), when="setup"),
        report,
    )

    assert report.outcome == "skipped"


def test_no_matchers_left_untouched():
    report = _xfail_report()
    _refine_report(_item(None), _call(exc=IndexError("x")), report)

    assert report.outcome == "skipped"


def test_report_that_is_not_xfail_left_untouched():
    report = SimpleNamespace(outcome="failed")  # no wasxfail attribute
    _refine_report(_item([(IndexError, None, True)]), _call(exc=IndexError("x")), report)

    assert report.outcome == "failed"
    assert not hasattr(report, "wasxfail")


# --------------------------------------------------------------------------- #
# Type matching                                                               #
# --------------------------------------------------------------------------- #


def test_matching_type_keeps_xfail():
    report = _xfail_report()
    _refine_report(_item([(IndexError, None, True)]), _call(exc=IndexError("boom")), report)

    assert report.outcome == "skipped"
    assert report.wasxfail == "open bug AP-1"


def test_wrong_type_downgraded_to_failure():
    report = _xfail_report()
    _refine_report(_item([(IndexError, None, True)]), _call(exc=ValueError("boom")), report)

    assert report.outcome == "failed"
    assert not hasattr(report, "wasxfail")


def test_subclass_of_expected_type_keeps_xfail():
    class MyError(ValueError):
        pass

    report = _xfail_report()
    _refine_report(_item([(ValueError, None, True)]), _call(exc=MyError("boom")), report)

    assert report.outcome == "skipped"


# --------------------------------------------------------------------------- #
# Message (error_contains) matching                                           #
# --------------------------------------------------------------------------- #


def test_message_substring_match_keeps_xfail():
    report = _xfail_report()
    _refine_report(
        _item([(IndexError, ["out of range"], True)]),
        _call(exc=IndexError("list index out of range")),
        report,
    )

    assert report.outcome == "skipped"


def test_message_substring_mismatch_downgraded():
    report = _xfail_report()
    _refine_report(
        _item([(IndexError, ["totally different"], True)]),
        _call(exc=IndexError("list index out of range")),
        report,
    )

    assert report.outcome == "failed"


def test_case_sensitive_wrong_case_downgraded():
    report = _xfail_report()
    _refine_report(
        _item([(IndexError, ["OUT OF RANGE"], True)]),
        _call(exc=IndexError("list index out of range")),
        report,
    )

    assert report.outcome == "failed"


def test_case_insensitive_wrong_case_keeps_xfail():
    report = _xfail_report()
    _refine_report(
        _item([(IndexError, ["OUT OF RANGE"], False)]),
        _call(exc=IndexError("list index out of range")),
        report,
    )

    assert report.outcome == "skipped"


# --------------------------------------------------------------------------- #
# Multiple matchers (several @bug decorators)                                 #
# --------------------------------------------------------------------------- #


def test_multiple_matchers_one_matches_keeps_xfail():
    matchers = [(KeyError, ["foo"], True), (IndexError, ["index"], True)]
    report = _xfail_report()
    _refine_report(_item(matchers), _call(exc=IndexError("list index out of range")), report)

    assert report.outcome == "skipped"


def test_multiple_matchers_none_match_downgraded():
    matchers = [(KeyError, ["foo"], True), (IndexError, ["nope"], True)]
    report = _xfail_report()
    _refine_report(_item(matchers), _call(exc=IndexError("list index out of range")), report)

    assert report.outcome == "failed"
