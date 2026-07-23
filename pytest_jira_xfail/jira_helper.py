from typing import List

import pytest
from _pytest.mark import Mark
from jira import JIRA
from requests import *
from selenium.common.exceptions import *
from singleton_decorator import singleton

from pytest_jira_xfail.xfail_plugin import (
    MATCHERS_ATTR,
    register_error_contains_plugin,
)

try:
    from playwright._impl._api_types import *
except ImportError:
    from playwright.sync_api import *


@singleton
class PytestJiraHelper:
    def __init__(
        self,
        jira_url: str,
        jira_username: str,
        jira_api_token: str,
        resolved_statuses: list = None,
    ):
        """

        :param jira_url: Specify your Jira URL
        :param jira_username:
        :param jira_api_token:
        :param resolved_statuses:
        """
        self.__jira_url = jira_url
        self.__jira_username = jira_username
        self.__jira_api_token = jira_api_token
        self.__custom_resolved_statuses = resolved_statuses
        self.parsed_issues: set = set()
        self.open_issues: set = set()

    @property
    def _resolved_statuses(self):
        statuses = ["Done", "Closed"]
        if self.__custom_resolved_statuses:
            statuses = self.__custom_resolved_statuses

        return statuses

    @property
    def _client(self):
        user = self.__jira_username
        apikey = self.__jira_api_token
        options = {"server": self.__jira_url}
        return JIRA(options, basic_auth=(user, apikey))

    def __is_issue_resolved(self, issue_key: str) -> bool:
        if issue_key in self.open_issues:
            return True

        status = self._client.issue(issue_key).fields.status.name
        if status in self._resolved_statuses:
            return True
        return False

    def __process_issue(self, issue_key: str):
        if issue_key not in self.parsed_issues:
            self.parsed_issues.add(issue_key)

            if not self.__is_issue_resolved(issue_key):
                self.open_issues.add(issue_key)

    def _check_if_issue_open(self, issue_key: str) -> bool:
        """Check if JIRA issue is actual/open

        Parameters
        ----------
        issue_key: Jira issue key including a project (e.g. "AP-123")
        """
        self.__process_issue(issue_key)
        return issue_key in self.open_issues

    def _get_issue_link(self, issue_key: str) -> str:
        """Get the issue full link

        Parameters
        ----------
        issue_key: Jira issue key including a project (e.g. "AP-123")
        """
        return f"{self.__jira_url}/browse/{issue_key}"

    def process_linked_jira_issues(self, items):
        """Process all Jira issues linked to tests (items) selected to run.
        Issues statuses will be defined and recorded.

        :param items: Current PyTest session items (tests)
        """

        for item in items:
            _add_allure_issue_labels(item)
            matchers = _get_bug_matchers(item)
            exceptions: tuple = tuple(exc_type for exc_type, _, _ in matchers)
            open_issues = []
            # The test is executed unless at least one open bug is marked run=False.
            run = True
            for mark in _get_bug_markers(item):
                key = mark.args[0]
                if self._check_if_issue_open(key):
                    open_issues.append(key)
                    if not mark.kwargs.get("run", True):
                        run = False

            if open_issues:
                links = "\n".join(self._get_issue_link(x) for x in open_issues)
                xfail_message = (
                    f"The test is skipped because of open issues:\n{links}\n"
                )

                mark = pytest.mark.xfail(
                    reason=xfail_message, raises=exceptions, run=run
                )
                item.add_marker(mark)
                item.add_marker(pytest.mark.issue)

                # If any linked bug expects a specific error message, refine the
                # native xfail with a runtime message check.
                if any(substrings for _, substrings, _ in matchers):
                    setattr(item, MATCHERS_ATTR, matchers)
                    register_error_contains_plugin(item.session.config)

    @staticmethod
    def get_all_linked_issues(items) -> List[str]:
        """Get keys of all Jira issues linked to tests  selected to run (as @bug or @issue)

        Parameters
        ----------
        :param items: Current PyTest session items (tests)
        """
        all_linked_issues = set()
        for item in items:
            bugs_labels = _get_bug_markers(item)
            issues_labels = list(
                filter(
                    lambda x: x.kwargs.get("label_type") == "issue", item.own_markers
                )
            )
            issues_keys = [x.args[0] for x in bugs_labels + issues_labels]
            all_linked_issues.update(issues_keys)

        return list(all_linked_issues)


def _get_bug_markers(item):
    """Get all @bug markers attached to the current test"""
    return list(
        filter(lambda x: x.kwargs.get("label_type") == "bug", item.own_markers)
    )


def _add_allure_issue_labels(item):
    """Add 'issue' label to the Allure report"""
    issues_labels = _get_bug_markers(item)
    issues_keys = [x.args[0] for x in issues_labels]
    for issue_key in issues_keys:
        item.own_markers.append(
            Mark(name="allure_label", args=(issue_key,), kwargs={"label_type": "issue"})
        )

    return issues_keys


def _normalize_error_contains(value):
    """Normalize the ``error_contains`` value to a list of substrings or None"""
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return list(value)


def _get_bug_matchers(item):
    """Get the error matchers attached to the current test.

    Returns a list of ``(exception_type, substrings_or_None, case_sensitive)``
    tuples, one per @bug marker, where ``substrings`` is a list of expected
    message substrings (or None when only the exception type should be matched).
    """
    matchers = []
    for mark in _get_bug_markers(item):
        exc_type = eval(mark.args[1])
        substrings = _normalize_error_contains(mark.kwargs.get("error_contains"))
        case_sensitive = mark.kwargs.get("case_sensitive", True)
        matchers.append((exc_type, substrings, case_sensitive))
    return matchers


def _get_expected_exception(item):
    """Get the expected exception type attached to the current test"""
    return tuple(exc_type for exc_type, _, _ in _get_bug_matchers(item))
