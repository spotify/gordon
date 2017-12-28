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
    """
    Load prod and user config.
    """
    conf_file = tmpdir.mkdir('config').join('gordon{}.toml'.format(suffix))
    conf_file.write(config_file)
    config = main._load_config(root=conf_file.dirpath())

    assert loaded_config == config


def test_load_config_raises(tmpdir):
    """
    No config loaded raises IOError.
    """
    dir_with_no_conf = tmpdir.mkdir('config')
    with pytest.raises(IOError) as e:
        main._load_config(root=dir_with_no_conf.dirpath())

    assert e.match('Cannot load Gordon configuration file from')


def test_setup(tmpdir, mocker, monkeypatch, config_file, loaded_config):
    """
    Setup service config and logging.
    """
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
# Tests for running service
#####
run_args = 'has_active_plugins,exp_log_count'
run_params = [
    (True, 2),
    (False, 1),
]


@pytest.mark.parametrize(run_args, run_params)
def test_run(has_active_plugins, exp_log_count, plugins, mocker,
             monkeypatch, caplog):
    """
    Successfully start the Gordon service.
    """
    setup_mock = mocker.MagicMock(main.setup, autospec=True)
    monkeypatch.setattr(main, 'setup', setup_mock)

    if has_active_plugins:
        load_plugins_mock = mocker.MagicMock(
            main.plugins_loader.load_plugins, autospec=True)
        load_plugins_mock.return_value = plugins
        monkeypatch.setattr(
            main.plugins_loader, 'load_plugins', load_plugins_mock)

    runner = CliRunner()
    result = runner.invoke(main.run)

    assert 0 == result.exit_code
    setup_mock.assert_called_once()
    assert exp_log_count == len(caplog.records)
