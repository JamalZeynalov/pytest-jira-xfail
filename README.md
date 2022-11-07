# pytest-jira-xfail

Plugin skips (xfail) test if it's linked to unresolved Jira issue(s)

## 1. Generate your Jira API token

You should have Jira user
with [API token generated](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/)

## 2. Add PytestJiraHelper to your pytest hook:

```python
import pytest

from pytest_jira_xfail.jira_helper import PytestJiraHelper


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    jira = PytestJiraHelper(
        jira_url="https://company.atlassian.net",
        jira_username="my_jira_user@company.com",
        jira_api_token="my_jira_user_api_token",
    )
    jira.process_linked_jira_issues(items)
```

## 3. Link bugs to your tests

```python
from pytest_jira_xfail.annotations import bug


@bug("MP-123")
def test_my_test_fails():
    assert False


@bug("MP-124", IndexError)
def test_my_test_broken():
    db_records = []
    assert db_records[0]


@bug("MP-124")
@bug("MP-124", IndexError)
def test_multiple_exceptions():
    db_records = []
    assert db_records[0][0] == 'active'
```

XFAIL message format:

```
XFAIL The test is skipped because of open bugs:
https://company.atlassian.net/browse/MP-123
```

## 4. [Optional] Set custom resolved statuses

By default, only issues with the status "Done" and "Closed" are considered resolved.
But you can override this list with your own:

```python
import pytest

from pytest_jira_xfail.jira_helper import PytestJiraHelper


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    jira = PytestJiraHelper(
        jira_url="https://company.atlassian.net",
        jira_username="my_jira_user@company.com",
        jira_api_token="my_jira_user_api_token",
        resolved_statuses=["Done", "Closed", "Released", "Declined"]
    )
    jira.process_linked_jira_issues(items)
```