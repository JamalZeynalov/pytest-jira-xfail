"""Unit tests for the runtime xfail veto ``_veto_xfail_if_error_unexpected``.

The refiner decides whether an injected xfail stays in effect or is cancelled
(so the test becomes a real FAILURE) based on the exception actually raised. It
does this by clearing pytest's ``xfailed`` stash entry *before* pytest-core
skipping evaluates it. We test the pure decision function directly with a real
``Stash`` instead of a live pytest run.
"""

from types import SimpleNamespace

from _pytest.skipping import xfailed_key
from _pytest.stash import Stash

import pytest_jira_xfail.xfail_plugin as xp
from pytest_jira_xfail.xfail_plugin import (
    MATCHERS_ATTR,
    _matcher_accepts_soft,
    _soft_failures_all_expected,
    _veto_xfail_if_error_unexpected,
)


def _item(matchers=None, xfailed=True):
    item = SimpleNamespace(stash=Stash())
    if matchers is not None:
        setattr(item, MATCHERS_ATTR, matchers)
    if xfailed:
        # Any truthy object stands in for pytest's Xfailed decision.
        item.stash[xfailed_key] = object()
    return item


def _call(exc=None, when="call"):
    excinfo = SimpleNamespace(value=exc) if exc is not None else None
    return SimpleNamespace(when=when, excinfo=excinfo)


def _xfail_kept(item):
    return item.stash.get(xfailed_key, None) is not None


# --------------------------------------------------------------------------- #
# No-op cases: the xfail decision is left exactly as pytest made it            #
# --------------------------------------------------------------------------- #


def test_no_exception_leaves_xfail_untouched():
    item = _item([(IndexError, None, True)])
    _veto_xfail_if_error_unexpected(item, _call(exc=None))

    assert _xfail_kept(item)


def test_non_call_phase_left_untouched():
    item = _item([(IndexError, None, True)])
    _veto_xfail_if_error_unexpected(item, _call(exc=IndexError("x"), when="setup"))

    assert _xfail_kept(item)


def test_no_matchers_left_untouched():
    item = _item(None)
    _veto_xfail_if_error_unexpected(item, _call(exc=IndexError("x")))

    assert _xfail_kept(item)


def test_not_going_to_xfail_is_left_untouched():
    item = _item([(IndexError, None, True)], xfailed=False)
    _veto_xfail_if_error_unexpected(item, _call(exc=IndexError("x")))

    assert not _xfail_kept(item)  # stays not-xfailed


# --------------------------------------------------------------------------- #
# Type matching                                                               #
# --------------------------------------------------------------------------- #


def test_matching_type_keeps_xfail():
    item = _item([(IndexError, None, True)])
    _veto_xfail_if_error_unexpected(item, _call(exc=IndexError("boom")))

    assert _xfail_kept(item)


def test_wrong_type_cancels_xfail():
    item = _item([(IndexError, None, True)])
    _veto_xfail_if_error_unexpected(item, _call(exc=ValueError("boom")))

    assert not _xfail_kept(item)


def test_subclass_of_expected_type_keeps_xfail():
    class MyError(ValueError):
        pass

    item = _item([(ValueError, None, True)])
    _veto_xfail_if_error_unexpected(item, _call(exc=MyError("boom")))

    assert _xfail_kept(item)


# --------------------------------------------------------------------------- #
# Message (error_contains) matching                                           #
# --------------------------------------------------------------------------- #


def test_message_substring_match_keeps_xfail():
    item = _item([(IndexError, ["out of range"], True)])
    _veto_xfail_if_error_unexpected(
        item, _call(exc=IndexError("list index out of range"))
    )

    assert _xfail_kept(item)


def test_message_substring_mismatch_cancels_xfail():
    item = _item([(IndexError, ["totally different"], True)])
    _veto_xfail_if_error_unexpected(
        item, _call(exc=IndexError("list index out of range"))
    )

    assert not _xfail_kept(item)


def test_case_sensitive_wrong_case_cancels_xfail():
    item = _item([(IndexError, ["OUT OF RANGE"], True)])
    _veto_xfail_if_error_unexpected(
        item, _call(exc=IndexError("list index out of range"))
    )

    assert not _xfail_kept(item)


def test_case_insensitive_wrong_case_keeps_xfail():
    item = _item([(IndexError, ["OUT OF RANGE"], False)])
    _veto_xfail_if_error_unexpected(
        item, _call(exc=IndexError("list index out of range"))
    )

    assert _xfail_kept(item)


# --------------------------------------------------------------------------- #
# Multiple matchers (several @bug decorators)                                 #
# --------------------------------------------------------------------------- #


def test_multiple_matchers_one_matches_keeps_xfail():
    matchers = [(KeyError, ["foo"], True), (IndexError, ["index"], True)]
    item = _item(matchers)
    _veto_xfail_if_error_unexpected(
        item, _call(exc=IndexError("list index out of range"))
    )

    assert _xfail_kept(item)


def test_multiple_matchers_none_match_cancels_xfail():
    matchers = [(KeyError, ["foo"], True), (IndexError, ["nope"], True)]
    item = _item(matchers)
    _veto_xfail_if_error_unexpected(
        item, _call(exc=IndexError("list index out of range"))
    )

    assert not _xfail_kept(item)


# --- Default @bug("KEY") behaviour (raises=AssertionError), as used in prod --- #


def test_default_assertion_error_keeps_xfail():
    # A bare @bug("KEY") tracks a hard-assertion failure -> stays XFAIL.
    item = _item([(AssertionError, None, True)])
    _veto_xfail_if_error_unexpected(item, _call(exc=AssertionError("assert 404 == 200")))

    assert _xfail_kept(item)


def test_non_assertion_crash_is_not_hidden_by_default_bug():
    # An unrelated crash (not an AssertionError) must surface as a real failure,
    # not be swallowed by the open bug's xfail.
    item = _item([(AssertionError, None, True)])
    _veto_xfail_if_error_unexpected(item, _call(exc=ConnectionError("unreachable")))

    assert not _xfail_kept(item)


# --------------------------------------------------------------------------- #
# error_contains with a partially-matching parametrization (issue: Allure     #
# showed a real failure as "skipped")                                         #
# --------------------------------------------------------------------------- #


def test_error_contains_matching_param_keeps_xfail():
    item = _item([(AssertionError, ["buildingCeilingHeight"], True)])
    _veto_xfail_if_error_unexpected(
        item, _call(exc=AssertionError("no buildingCeilingHeight"))
    )

    assert _xfail_kept(item)


def test_error_contains_non_matching_param_cancels_xfail():
    item = _item([(AssertionError, ["buildingCeilingHeight"], True)])
    _veto_xfail_if_error_unexpected(
        item, _call(exc=AssertionError("nothing to raise"))
    )

    assert not _xfail_kept(item)


# --------------------------------------------------------------------------- #
# Soft-assertion (pytest-check) failures: error_contains enforced on the       #
# collected failure messages (call.excinfo is None for soft failures).         #
# --------------------------------------------------------------------------- #


def test_soft_matcher_type_only_assertion_accepts_any_message():
    assert _matcher_accepts_soft((AssertionError, None, True), "whatever") is True


def test_soft_matcher_non_assertion_type_is_rejected():
    # Soft failures are AssertionError based; a KeyError matcher cannot apply.
    assert _matcher_accepts_soft((KeyError, None, True), "whatever") is False


def test_soft_matcher_substring_match_and_case():
    assert _matcher_accepts_soft((AssertionError, ["foo"], True), "a foo b") is True
    assert _matcher_accepts_soft((AssertionError, ["foo"], True), "a bar b") is False
    assert _matcher_accepts_soft((AssertionError, ["FOO"], False), "a foo b") is True


def test_soft_all_expected_true_when_every_failure_matches():
    matchers = [(AssertionError, ["foo"], True)]
    assert _soft_failures_all_expected(["x foo", "y foo too"], matchers) is True


def test_soft_all_expected_false_when_any_failure_unexpected():
    matchers = [(AssertionError, ["foo"], True)]
    assert _soft_failures_all_expected(["x foo", "y bar"], matchers) is False


def test_veto_soft_failure_matching_keeps_xfail(monkeypatch):
    monkeypatch.setattr(
        xp, "_collect_soft_failures", lambda: ["differs for buildingCeilingHeight"]
    )
    item = _item([(AssertionError, ["buildingCeilingHeight"], True)])
    _veto_xfail_if_error_unexpected(item, _call(exc=None))  # soft: no call-phase exc

    assert _xfail_kept(item)


def test_veto_soft_failure_not_matching_cancels_xfail(monkeypatch):
    monkeypatch.setattr(
        xp, "_collect_soft_failures", lambda: ["differs for tenantName"]
    )
    item = _item([(AssertionError, ["buildingCeilingHeight"], True)])
    _veto_xfail_if_error_unexpected(item, _call(exc=None))

    assert not _xfail_kept(item)


def test_veto_soft_failure_mixed_expected_and_unexpected_cancels(monkeypatch):
    # One failure matches the bug, another is unrelated -> surface a real failure.
    monkeypatch.setattr(
        xp,
        "_collect_soft_failures",
        lambda: ["diff buildingCeilingHeight", "diff tenantName"],
    )
    item = _item([(AssertionError, ["buildingCeilingHeight"], True)])
    _veto_xfail_if_error_unexpected(item, _call(exc=None))

    assert not _xfail_kept(item)


def test_veto_type_only_bug_keeps_xfail_for_soft_failure(monkeypatch):
    # A bare @bug (no error_contains) keeps the deterministic XFAIL for any soft
    # assertion, exactly as before.
    monkeypatch.setattr(xp, "_collect_soft_failures", lambda: ["any soft failure"])
    item = _item([(AssertionError, None, True)])
    _veto_xfail_if_error_unexpected(item, _call(exc=None))

    assert _xfail_kept(item)


def test_veto_no_soft_failures_keeps_xfail_for_xpass(monkeypatch):
    # The test actually passed (no soft failures) -> XPASS; xfail must be retained.
    monkeypatch.setattr(xp, "_collect_soft_failures", lambda: [])
    item = _item([(AssertionError, ["buildingCeilingHeight"], True)])
    _veto_xfail_if_error_unexpected(item, _call(exc=None))

    assert _xfail_kept(item)
