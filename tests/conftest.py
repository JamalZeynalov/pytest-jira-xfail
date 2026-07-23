# Enable the ``pytester`` fixture, used only by the pytest-check step-function
# end-to-end tests (tests/test_pytest_check_step_functions.py). All other tests
# are pure in-process unit tests and do not need it.
pytest_plugins = ["pytester"]
