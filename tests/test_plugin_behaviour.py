"""End-to-end behavioural tests for the plugin, driven through ``pytester``.

Naming convention used by the stubbed Jira conftest (see ``conftest.py``):
    * ``OPEN-*``  -> unresolved issue  (xfail should be applied)
    * ``DONE-*``  -> resolved issue    (test runs normally)
"""


# --------------------------------------------------------------------------- #
# Issue status                                                                 #
# --------------------------------------------------------------------------- #


def test_open_issue_failing_test_is_xfailed(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1")
        def test_it():
            assert False
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)


def test_open_issue_passing_test_is_xpassed(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1")
        def test_it():
            assert True
        """
    )
    jira_pytester.runpytest().assert_outcomes(xpassed=1)


def test_resolved_issue_failing_test_really_fails(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("DONE-1")
        def test_it():
            assert False
        """
    )
    jira_pytester.runpytest().assert_outcomes(failed=1)


def test_resolved_issue_passing_test_passes(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("DONE-1")
        def test_it():
            assert True
        """
    )
    jira_pytester.runpytest().assert_outcomes(passed=1)


def test_test_without_bug_marker_runs_normally(jira_pytester):
    jira_pytester.makepyfile(
        """
        def test_it():
            assert True
        """
    )
    jira_pytester.runpytest().assert_outcomes(passed=1)


def test_mixed_open_and_resolved_issues_applies_xfail(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("DONE-1")
        @bug("OPEN-2")
        def test_it():
            assert False
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)


# --------------------------------------------------------------------------- #
# Exception type matching (raises)                                             #
# --------------------------------------------------------------------------- #


def test_matching_exception_type_is_xfailed(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", IndexError)
        def test_it():
            [][0]
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)


def test_non_matching_exception_type_fails(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", IndexError)
        def test_it():
            raise ValueError("boom")
        """
    )
    jira_pytester.runpytest().assert_outcomes(failed=1)


def test_multiple_bug_markers_accept_several_exception_types(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1")
        @bug("OPEN-2", IndexError)
        def test_it():
            [][0]
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)


# --------------------------------------------------------------------------- #
# run flag                                                                     #
# --------------------------------------------------------------------------- #


def test_run_true_executes_the_test(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", run=True)
        def test_it():
            assert False
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)


def test_run_false_never_executes_the_test(jira_pytester):
    # The body raises AssertionError, which would NOT match raises=RuntimeError.
    # If the test were executed it would be a real failure; getting XFAIL proves
    # the body was never run.
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", RuntimeError, run=False)
        def test_it():
            assert False
        """
    )
    result = jira_pytester.runpytest("-rxX")
    result.assert_outcomes(xfailed=1)
    result.stdout.fnmatch_lines(["*NOTRUN*"])


# --------------------------------------------------------------------------- #
# error_contains: message matching                                            #
# --------------------------------------------------------------------------- #


def test_error_contains_message_matches_is_xfailed(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", IndexError, error_contains="list index out of range")
        def test_it():
            [][0]
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)


def test_error_contains_message_mismatch_fails(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", IndexError, error_contains="a different message")
        def test_it():
            [][0]
        """
    )
    jira_pytester.runpytest().assert_outcomes(failed=1)


def test_error_contains_list_any_substring_matches_is_xfailed(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", KeyError, error_contains=["foo", "bar"])
        def test_it():
            raise KeyError("value contains bar somewhere")
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)


def test_error_contains_list_no_substring_matches_fails(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", KeyError, error_contains=["foo", "baz"])
        def test_it():
            raise KeyError("value contains bar somewhere")
        """
    )
    jira_pytester.runpytest().assert_outcomes(failed=1)


def test_error_contains_wrong_type_fails(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", KeyError, error_contains="anything")
        def test_it():
            raise ValueError("anything")
        """
    )
    jira_pytester.runpytest().assert_outcomes(failed=1)


def test_error_contains_passing_test_is_xpassed(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", IndexError, error_contains="whatever")
        def test_it():
            assert True
        """
    )
    jira_pytester.runpytest().assert_outcomes(xpassed=1)


def test_run_false_short_circuits_error_contains(jira_pytester):
    # Message would NOT match if the test ran, but run=False skips execution,
    # so the test is XFAIL (NOTRUN) rather than a failure.
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", IndexError, error_contains="never checked", run=False)
        def test_it():
            [][0]
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)


# --------------------------------------------------------------------------- #
# case sensitivity                                                            #
# --------------------------------------------------------------------------- #


def test_case_sensitive_default_exact_case_is_xfailed(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", IndexError, error_contains="list index out of range")
        def test_it():
            [][0]
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)


def test_case_sensitive_default_wrong_case_fails(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", IndexError, error_contains="LIST INDEX OUT OF RANGE")
        def test_it():
            [][0]
        """
    )
    jira_pytester.runpytest().assert_outcomes(failed=1)


def test_case_insensitive_matches_regardless_of_case(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug(
            "OPEN-1",
            IndexError,
            error_contains="LIST INDEX OUT OF RANGE",
            case_sensitive=False,
        )
        def test_it():
            [][0]
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)


# --------------------------------------------------------------------------- #
# Multiple markers combined with error_contains                               #
# --------------------------------------------------------------------------- #


def test_multiple_markers_message_matches_one_is_xfailed(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", KeyError, error_contains="foo")
        @bug("OPEN-2", IndexError, error_contains="list index")
        def test_it():
            [][0]
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=1)


def test_multiple_markers_no_message_matches_fails(jira_pytester):
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1", KeyError, error_contains="foo")
        @bug("OPEN-2", IndexError, error_contains="not in message")
        def test_it():
            [][0]
        """
    )
    jira_pytester.runpytest().assert_outcomes(failed=1)


def test_injected_xfail_marker_has_no_raises(jira_pytester):
    # Regression guard for issue #3. The injected xfail marker must NOT carry a
    # ``raises=`` kwarg: with it, pytest-check classifies soft-assertion failures
    # by string-matching the rendered traceback (environment/xdist-dependent).
    # The expected exception type is enforced by our runtime refiner instead.
    #
    # This guard is environment-independent: the test's own assertions pass, so
    # with an open bug it is XPASS. If a regression re-introduced ``raises=``, the
    # inner assertion would fail and the marker would turn it into XFAIL instead,
    # making ``assert_outcomes(xpassed=1)`` fail.
    jira_pytester.makepyfile(
        """
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1")
        def test_it(request):
            marker = request.node.get_closest_marker("xfail")
            assert marker is not None
            assert "raises" not in marker.kwargs, marker.kwargs
        """
    )
    jira_pytester.runpytest().assert_outcomes(xpassed=1)


def test_parametrized_test_with_open_issue(jira_pytester):
    jira_pytester.makepyfile(
        """
        import pytest
        from pytest_jira_xfail.annotations import bug

        @bug("OPEN-1")
        @pytest.mark.parametrize("value", [0, 1, 2])
        def test_it(value):
            assert value < 0
        """
    )
    jira_pytester.runpytest().assert_outcomes(xfailed=3)
