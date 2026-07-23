"""Unit tests for the internal helper functions (no pytest sub-session)."""

import pytest
from _pytest.mark import Mark

from pytest_jira_xfail.jira_helper import (
    PytestJiraHelper,
    _get_bug_matchers,
    _normalize_error_contains,
)
from pytest_jira_xfail.xfail_plugin import _message_contains

# ``PytestJiraHelper`` is wrapped by @singleton; reach the real class for the
# static utility method.
JiraHelper = PytestJiraHelper.__wrapped__


class _FakeItem:
    """Minimal stand-in for a pytest item, exposing only ``own_markers``."""

    def __init__(self, markers):
        self.own_markers = markers


def _bug_mark(key, exc="AssertionError", **kwargs):
    return Mark(
        name="allure_label",
        args=(key, exc),
        kwargs={"label_type": "bug", **kwargs},
    )


def _issue_mark(key):
    return Mark(name="allure_label", args=(key,), kwargs={"label_type": "issue"})


# --------------------------------------------------------------------------- #
# _normalize_error_contains                                                    #
# --------------------------------------------------------------------------- #


def test_normalize_none_returns_none():
    assert _normalize_error_contains(None) is None


def test_normalize_str_wraps_in_list():
    assert _normalize_error_contains("boom") == ["boom"]


def test_normalize_list_is_copied():
    original = ["a", "b"]
    result = _normalize_error_contains(original)
    assert result == ["a", "b"]
    assert result is not original


def test_normalize_tuple_becomes_list():
    assert _normalize_error_contains(("a", "b")) == ["a", "b"]


# --------------------------------------------------------------------------- #
# _message_contains                                                            #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "message, substrings, case_sensitive, expected",
    [
        ("Hello World", ["World"], True, True),
        ("Hello World", ["world"], True, False),
        ("Hello World", ["world"], False, True),
        ("Hello World", ["WORLD"], False, True),
        ("abc", ["x", "b"], True, True),
        ("abc", ["x", "y"], True, False),
        ("abc", ["X", "B"], False, True),
    ],
)
def test_message_contains(message, substrings, case_sensitive, expected):
    assert _message_contains(message, substrings, case_sensitive) is expected


# --------------------------------------------------------------------------- #
# _get_bug_matchers                                                            #
# --------------------------------------------------------------------------- #


def test_get_bug_matchers_defaults():
    item = _FakeItem([_bug_mark("AP-1", "IndexError")])
    matchers = _get_bug_matchers(item)
    assert matchers == [(IndexError, None, True)]


def test_get_bug_matchers_with_error_contains_and_case():
    item = _FakeItem(
        [
            _bug_mark(
                "AP-1",
                "KeyError",
                error_contains=["foo", "bar"],
                case_sensitive=False,
            )
        ]
    )
    matchers = _get_bug_matchers(item)
    assert matchers == [(KeyError, ["foo", "bar"], False)]


def test_get_bug_matchers_ignores_non_bug_markers():
    item = _FakeItem([_issue_mark("AP-2"), _bug_mark("AP-1", "ValueError")])
    matchers = _get_bug_matchers(item)
    assert matchers == [(ValueError, None, True)]


# --------------------------------------------------------------------------- #
# get_all_linked_issues                                                        #
# --------------------------------------------------------------------------- #


def test_get_all_linked_issues_collects_bugs_and_issues():
    items = [
        _FakeItem([_bug_mark("AP-1")]),
        _FakeItem([_issue_mark("AP-2"), _bug_mark("AP-3")]),
        _FakeItem([]),
    ]
    result = JiraHelper.get_all_linked_issues(items)
    assert set(result) == {"AP-1", "AP-2", "AP-3"}


def test_get_all_linked_issues_empty_when_no_markers():
    assert JiraHelper.get_all_linked_issues([_FakeItem([])]) == []
