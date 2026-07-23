"""Unit tests for ``PytestJiraHelper.process_linked_jira_issues``.

These drive the collection-time logic directly with lightweight fakes instead of
spinning up nested pytest sessions: we call the method on a fresh helper (Jira
stubbed) and inspect the markers it injects onto the item.
"""

from types import SimpleNamespace

from _pytest.mark import Mark

from pytest_jira_xfail.jira_helper import PytestJiraHelper
from pytest_jira_xfail.xfail_plugin import MATCHERS_ATTR

# ``PytestJiraHelper`` is wrapped by @singleton; the real class gives us a fresh,
# isolated instance per test.
JiraHelper = PytestJiraHelper.__wrapped__


class _FakePluginManager:
    def __init__(self):
        self.registered = {}

    def has_plugin(self, name):
        return name in self.registered

    def register(self, plugin, name):
        self.registered[name] = plugin


class _FakeItem:
    """Minimal pytest item: holds markers and records ``add_marker`` calls."""

    def __init__(self, markers):
        self.own_markers = list(markers)
        self.added_markers = []
        self.session = SimpleNamespace(
            config=SimpleNamespace(pluginmanager=_FakePluginManager())
        )

    def add_marker(self, marker):
        mark = getattr(marker, "mark", marker)  # unwrap MarkDecorator
        self.own_markers.append(mark)
        self.added_markers.append(mark)


def _bug(key, exc="AssertionError", **kwargs):
    return Mark(
        name="allure_label",
        args=(key, exc),
        kwargs={"label_type": "bug", **kwargs},
    )


def _helper(open_keys):
    helper = JiraHelper("http://jira.test", "user", "token")
    helper._check_if_issue_open = lambda key: key in open_keys
    return helper


def _xfail_markers(item):
    return [m for m in item.added_markers if m.name == "xfail"]


# --------------------------------------------------------------------------- #
# Open issue -> xfail injected                                                 #
# --------------------------------------------------------------------------- #


def test_open_issue_injects_single_xfail_marker():
    item = _FakeItem([_bug("AP-1")])
    _helper({"AP-1"}).process_linked_jira_issues([item])

    xfails = _xfail_markers(item)
    assert len(xfails) == 1
    assert "AP-1" in xfails[0].kwargs["reason"]
    assert xfails[0].kwargs["run"] is True


def test_injected_xfail_marker_has_no_raises():
    # Regression guard for issue #3: passing raises= makes pytest-check classify
    # soft-assertion failures by string-matching the rendered traceback, which is
    # environment/xdist-dependent. The type is enforced by the runtime refiner.
    item = _FakeItem([_bug("AP-1", "IndexError")])
    _helper({"AP-1"}).process_linked_jira_issues([item])

    assert "raises" not in _xfail_markers(item)[0].kwargs


def test_open_issue_adds_issue_marker():
    item = _FakeItem([_bug("AP-1")])
    _helper({"AP-1"}).process_linked_jira_issues([item])

    assert any(m.name == "issue" for m in item.added_markers)


def test_open_issue_attaches_matchers_and_registers_refiner():
    item = _FakeItem([_bug("AP-1", "IndexError")])
    helper = _helper({"AP-1"})
    helper.process_linked_jira_issues([item])

    assert getattr(item, MATCHERS_ATTR) == [(IndexError, None, True)]
    assert item.session.config.pluginmanager.registered  # refiner registered


def test_error_contains_and_case_flow_into_matchers():
    item = _FakeItem(
        [_bug("AP-1", "KeyError", error_contains=["foo", "bar"], case_sensitive=False)]
    )
    _helper({"AP-1"}).process_linked_jira_issues([item])

    assert getattr(item, MATCHERS_ATTR) == [(KeyError, ["foo", "bar"], False)]


def test_run_false_sets_run_false_on_marker():
    item = _FakeItem([_bug("AP-1", run=False)])
    _helper({"AP-1"}).process_linked_jira_issues([item])

    assert _xfail_markers(item)[0].kwargs["run"] is False


def test_run_false_when_any_open_bug_requests_it():
    item = _FakeItem([_bug("AP-1"), _bug("AP-2", run=False)])
    _helper({"AP-1", "AP-2"}).process_linked_jira_issues([item])

    assert _xfail_markers(item)[0].kwargs["run"] is False


def test_mixed_open_and_resolved_still_injects_xfail():
    item = _FakeItem([_bug("DONE-1"), _bug("OPEN-2")])
    _helper({"OPEN-2"}).process_linked_jira_issues([item])

    assert len(_xfail_markers(item)) == 1


# --------------------------------------------------------------------------- #
# Resolved issue -> nothing injected                                          #
# --------------------------------------------------------------------------- #


def test_resolved_issue_injects_no_xfail():
    item = _FakeItem([_bug("AP-1")])
    _helper(set()).process_linked_jira_issues([item])

    assert _xfail_markers(item) == []
    assert not hasattr(item, MATCHERS_ATTR)


def test_no_bug_marker_injects_nothing():
    item = _FakeItem([])
    _helper(set()).process_linked_jira_issues([item])

    assert item.added_markers == []
