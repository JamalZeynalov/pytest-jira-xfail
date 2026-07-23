"""Test configuration for the pytest-jira-xfail plugin.

The behavioural tests use pytest's own ``pytester`` fixture to run a throwaway
pytest session against generated test files, so we can assert on real outcomes
(xfailed / failed / xpassed / passed) produced by the plugin.

Jira is never contacted: the generated ``conftest.py`` stubs
``PytestJiraHelper._check_if_issue_open`` so that any issue key starting with
``OPEN`` is treated as an open (unresolved) issue and everything else (e.g.
``DONE-1``) is treated as resolved.
"""

import pytest

pytest_plugins = ["pytester"]

# conftest injected into every generated sub-project.
JIRA_CONFTEST = """
from pytest_jira_xfail.jira_helper import PytestJiraHelper


def pytest_collection_modifyitems(items):
    helper = PytestJiraHelper("http://jira.test", "user", "token")
    # Treat issues whose key starts with "OPEN" as unresolved, without Jira.
    helper._check_if_issue_open = lambda key: key.startswith("OPEN")
    helper.process_linked_jira_issues(items)
"""


@pytest.fixture
def jira_pytester(pytester):
    """A ``pytester`` instance pre-configured with the stubbed Jira conftest."""
    pytester.makeconftest(JIRA_CONFTEST)
    # Disable pytest-playwright in the nested session too: it wraps each test in
    # a soft-assertion scope that we neither need nor want here.
    pytester.makeini("[pytest]\naddopts = -p no:playwright\n")
    return pytester
