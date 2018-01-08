# -*- coding: utf-8 -*-
#
# Copyright 2017 Spotify AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
from click.testing import CliRunner

from gordon import main


#####
# Tests for service setup
#####
@pytest.mark.parametrize('suffix', ['', '-user'])
def test_load_config(tmpdir, suffix, config_file, loaded_config):
    """Load prod and user config."""
    conf_file = tmpdir.mkdir('config').join('gordon{}.toml'.format(suffix))
    conf_file.write(config_file)
    config = main._load_config(root=conf_file.dirpath())

    assert loaded_config == config


def test_load_config_raises(tmpdir):
    """No config loaded raises IOError."""
    dir_with_no_conf = tmpdir.mkdir('config')
    with pytest.raises(IOError) as e:
        main._load_config(root=dir_with_no_conf.dirpath())

    assert e.match('Cannot load Gordon configuration file from')


def test_setup(tmpdir, mocker, monkeypatch, config_file, loaded_config):
    """Setup service config and logging."""
    conf_file = tmpdir.mkdir('config').join('gordon.toml')
    conf_file.write(config_file)

    ulogger_mock = mocker.MagicMock(main.ulogger, autospec=True)
    ulogger_mock.setup_logging = mocker.Mock()
    monkeypatch.setattr(main, 'ulogger', ulogger_mock)

    config = main.setup(config_root=conf_file.dirpath())

    assert loaded_config == config

    ulogger_mock.setup_logging.assert_called_once_with(
        progname='gordon', level='DEBUG', handlers=['stream'])


#####
# Tests & fixtures for running service
#####
@pytest.fixture
def setup_mock(mocker, monkeypatch):
    setup_mock = mocker.MagicMock(main.setup, autospec=True)
    monkeypatch.setattr(main, 'setup', setup_mock)
    return setup_mock


@pytest.fixture
def load_plugins_mock(mocker, monkeypatch):
    load_plugins_mock = mocker.MagicMock(
        main.plugins_loader.load_plugins, autospec=True)
    monkeypatch.setattr(main.plugins_loader, 'load_plugins', load_plugins_mock)
    return load_plugins_mock


def test_log_or_exit_on_exceptions_no_debug(plugin_exc_mock, mocker,
                                            monkeypatch):
    """Raise SystemExit if debug flag is off."""
    logging_mock = mocker.MagicMock(main.logging, autospec=True)
    monkeypatch.setattr(main, 'logging', logging_mock)

    errors = [('bad.plugin', plugin_exc_mock)]
    with pytest.raises(SystemExit) as e:
        main._log_or_exit_on_exceptions(errors, debug=False)

    e.match('1')
    logging_mock.error.assert_called_once()
    logging_mock.warn.assert_not_called()


def test_log_or_exit_on_exceptions_debug(plugin_exc_mock, mocker, monkeypatch):
    """Do not exit out if debug flag is on."""
    logging_mock = mocker.MagicMock(main.logging, autospec=True)
    monkeypatch.setattr(main, 'logging', logging_mock)

    errors = [('bad.plugin', plugin_exc_mock)]

    main._log_or_exit_on_exceptions(errors, debug=True)

    logging_mock.warn.assert_called_once()
    logging_mock.error.assert_not_called()


run_args = 'has_active_plugins,exp_log_count'
run_params = [
    (True, 2),
    (False, 1),
]


@pytest.mark.parametrize(run_args, run_params)
def test_run(has_active_plugins, exp_log_count, plugins, setup_mock,
             load_plugins_mock, mocker, monkeypatch, caplog):
    """Successfully start the Gordon service."""
    names, errors = [], []
    if has_active_plugins:
        names = ['one.plugin', 'two.plugin']
    load_plugins_mock.return_value = names, plugins, errors

    runner = CliRunner()
    result = runner.invoke(main.run)

    assert 0 == result.exit_code
    setup_mock.assert_called_once()
    assert exp_log_count == len(caplog.records)


def test_run_raise_exceptions(loaded_config, plugins, caplog, setup_mock,
                              load_plugins_mock, plugin_exc_mock,
                              monkeypatch, mocker):
    """Raise plugin exceptions when not in debug mode."""
    loaded_config['core']['debug'] = False
    setup_mock.return_value = loaded_config

    names = ['one.plugin', 'two.plugin']
    errors = [('three.plugin', plugin_exc_mock)]
    load_plugins_mock.return_value = names, plugins, errors

    runner = CliRunner()
    result = runner.invoke(main.run)

    assert 1 == result.exit_code
    setup_mock.assert_called_once()
    assert 1 == len(caplog.records)
