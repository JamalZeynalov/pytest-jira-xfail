from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="pytest-jira-xfail",
    version="0.0.4",
    author="Jamal Zeinalov",
    author_email="jamal.zeynalov@gmail.com",
    description='Plugin skips (xfail) tests if unresolved Jira issue(s) linked',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/JamalZeynalov/pytest-jira-xfail",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "pytest~=7.2.0",
        "requests~=2.28.1",
        "setuptools~=65.5.1",
        "jira~=3.4.1",
        "singleton-decorator~=1.0.0",
        "allure-pytest~=2.11.1",
    ],
    python_requires=">=3.9",
)
