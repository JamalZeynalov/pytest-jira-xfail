import pytest


def bug(issue_key: str, raises: type = AssertionError, run: bool = True):
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
    """
    # Equivalent to allure.label("bug", issue_key, raises.__name__) but with an
    # extra "run" kwarg that the plugin reads. Allure ignores unknown kwargs, so
    # its reporting is unaffected.
    return pytest.mark.allure_label(
        issue_key, raises.__name__, label_type="bug", run=run
    )
