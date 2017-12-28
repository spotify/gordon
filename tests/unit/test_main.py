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

from unittest import mock

import pytest
from click.testing import CliRunner

from gordon import main


#####
# Tests for service setup
#####
@pytest.mark.parametrize('suffix', ['', '-user'])
def test_load_config(tmpdir, suffix, config_file):
    """
    Load prod and user config.
    """
    conf_file = tmpdir.mkdir('config').join('gordon{}.toml'.format(suffix))
    conf_file.write(config_file)
    config = main._load_config(root=conf_file.dirpath())

    expected = {'logging': {'level': 'debug', 'handlers': ['stream']}}
    assert expected == config


def test_load_config_raises(tmpdir):
    """
    No config loaded raises IOError.
    """
    dir_with_no_conf = tmpdir.mkdir('config')
    with pytest.raises(IOError) as e:
        main._load_config(root=dir_with_no_conf.dirpath())

    assert e.match('Cannot load Gordon configuration file from')


def test_setup(tmpdir, monkeypatch, config_file):
    """
    Setup service config and logging.
    """
    conf_file = tmpdir.mkdir('config').join('gordon.toml')
    conf_file.write(config_file)

    ulogger_mock = mock.MagicMock(main.ulogger, autospec=True)
    ulogger_mock.setup_logging = mock.Mock()
    monkeypatch.setattr(main, 'ulogger', ulogger_mock)

    config = main.setup(conf_file.dirpath())

    expected = {'logging': {'level': 'debug', 'handlers': ['stream']}}
    assert expected == config

    ulogger_mock.setup_logging.assert_called_once_with(
        progname='gordon', level='DEBUG', handlers=['stream'])


#####
# Tests for running service
#####
def test_run(monkeypatch, caplog):
    """
    Successfully start the Gordon service.
    """
    setup_mock = mock.MagicMock(main.setup, autospec=True)
    monkeypatch.setattr(main, 'setup', setup_mock)

    runner = CliRunner()
    result = runner.invoke(main.run)

    assert 0 == result.exit_code
    setup_mock.assert_called_once()
    assert 1 == len(caplog.records)
