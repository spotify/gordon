# gordon

Event-driven Cloud DNS registration - a service to consume hostname change events and update records for a 3rd party DNS provider.

**NOTICE**: This is still in the planning phase and under active development. Gordon should not be used in production, yet.

## Requirements

For the initial release, the following will be supported:

* Python 3.6
* Googe Cloud Platform

Support for other Python versions and cloud providers may be added.

## Development

For development and running tests, your system must have all supported versions of Python installed. We suggest using [pyenv](https://github.com/yyuu/pyenv).

### Setup

```sh
$ git clone git@github.com:spotify/gordon.git && cd gordon
# make a virtualenv
(env) $ pip install -r dev-requirements.txt
```

### Running tests

To run the entire test suite:

```sh
# outside of the virtualenv
# if tox is not yet installed
$ pip install tox
$ tox
```

If you want to run the test suite for a specific version of Python:

```sh
# outside of the virtualenv
$ tox -e py36
```

To run an individual test, call `pytest` directly:

```sh
# inside virtualenv
(env) $ pytest tests/test_foo.py
```


## Code of Conduct

This project adheres to the [Open Code of Conduct][code-of-conduct]. By participating, you are expected to honor this code.

[code-of-conduct]: https://github.com/spotify/code-of-conduct/blob/master/code-of-conduct.md
