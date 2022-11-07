import allure


def bug(issue_key: str, raises: type = AssertionError):
    """Use this annotation when you need to xfail entire test until the bug is fixed.
    Warning: Failed runs of a parametrized test will be marked with XFAIL and passed as XPASS.

    Parameters
    ----------
    issue_key:
        Format of issue_key is: 'PN-123'
    raises:
        Expected error type. The test will fail if any other exception is raised.
        Use multiple @bug() annotation to specify several exceptions
    """
    return allure.label("bug", issue_key, raises.__name__)
