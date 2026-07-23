from typing import List, Union

import pytest


def bug(
    issue_key: str,
    raises: type = AssertionError,
    run: bool = True,
    error_contains: Union[str, List[str]] = None,
):
    """Use this annotation when you need to xfail entire test until the bug is fixed.
    Warning: Failed runs of a parametrized test will be marked with XFAIL and passed as XPASS.

    Parameters
    ----------
    issue_key:
        Format of issue_key is: 'PN-123'
    raises:
        Expected error type. The test will fail if any other exception is raised.
        Use multiple @bug() annotation to specify several exceptions
    run:
        Whether to still execute the test while the issue is open.
        Set to False to skip the test entirely (it will be reported as XFAIL but
        never executed). Defaults to True, which keeps the existing xfail behaviour.
    error_contains:
        A substring, or a list of substrings, expected in the raised error message.
        The test is treated as XFAIL only if the raised error both matches ``raises``
        and its message contains at least one of these substrings. If the type
        matches but the message does not, the test is reported as a real failure.
        Defaults to None, which matches on the error type only.
    """
    # Equivalent to allure.label("bug", issue_key, raises.__name__) but with extra
    # "run" and "error_contains" kwargs that the plugin reads. Allure ignores
    # unknown kwargs, so its reporting is unaffected.
    return pytest.mark.allure_label(
        issue_key,
        raises.__name__,
        label_type="bug",
        run=run,
        error_contains=error_contains,
    )
