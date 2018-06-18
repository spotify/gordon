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

import asyncio
import signal

import pytest
from click.testing import CliRunner

from gordon import main
from tests.unit import conftest


#####
# Tests for service shutdown
#####
@pytest.mark.asyncio
async def test_shutdown(mocker, monkeypatch, caplog, event_loop):
    async def foo():
        await asyncio.sleep(0)

    task = asyncio.Task(foo())
    mock_task = mocker.Mock()
    mock_task.all_tasks.return_value = [task]
    monkeypatch.setattr('gordon.main.asyncio.Task', mock_task)

    await main.shutdown(signal.SIGTERM, event_loop)

    assert 4 == len(caplog.records)
    assert task.cancelled()


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
def mock_plugins_loader(mocker, monkeypatch):
    mock_plugins_loader = mocker.MagicMock(
        main.plugins_loader.load_plugins, autospec=True)
    monkeypatch.setattr(
        main.plugins_loader, 'load_plugins', mock_plugins_loader)
    return mock_plugins_loader


def test_log_or_exit_on_exceptions_no_debug(plugin_exc_mock, mocker,
                                            monkeypatch):
    """Raise SystemExit if debug flag is off."""
    logging_mock = mocker.MagicMock(main.logging, autospec=True)
    monkeypatch.setattr(main, 'logging', logging_mock)

    errors = [('bad.plugin', plugin_exc_mock)]
    with pytest.raises(SystemExit) as e:
        main._log_or_exit_on_exceptions('base msg', errors, debug=False)

    e.match('1')
    logging_mock.error.assert_called_once()
    logging_mock.warn.assert_not_called()


def test_log_or_exit_on_exceptions_debug(plugin_exc_mock, mocker, monkeypatch):
    """Do not exit out if debug flag is on."""
    logging_mock = mocker.MagicMock(main.logging, autospec=True)
    monkeypatch.setattr(main, 'logging', logging_mock)

    errors = [('bad.plugin', plugin_exc_mock)]

    main._log_or_exit_on_exceptions('base msg', errors, debug=True)

    logging_mock.warn.assert_called_once()
    logging_mock.error.assert_not_called()


@pytest.fixture
def mock_log_or_exit_on_exc(mocker, monkeypatch):
    mock = mocker.Mock()
    monkeypatch.setattr('gordon.main._log_or_exit_on_exceptions', mock)
    return mock


@pytest.mark.parametrize('plugins,exp_log_calls', (
    (('event_consumer', 'enricher', 'publisher', 'runnable'), 0),
    (('event_consumer', 'enricher', 'publisher'), 0),
    (('runnable', 'enricher'), 0),
    (('runnable',), 1),
    (('event_consumer',), 0),
    (('enricher',), 1),

))
def test_assert_required_plugins(mocker, plugins, exp_log_calls,
                                 inited_plugins, mock_log_or_exit_on_exc):
    """Assert required plugins are installed, else warn/error out."""
    plugins = [inited_plugins[p] for p in plugins]
    main._gather_plugins_by_type(plugins, debug=True)

    assert exp_log_calls == mock_log_or_exit_on_exc.call_count


@pytest.mark.parametrize('patches,exp_mock_call', (
    # provider: async run; gen plugin: async run
    ([], 0),
    # provider: sync run; gen plugin: async run
    ([('EventConsumerStub.run', 'set')], 1),
    # provider: no run; gen plugin: async run
    ([('EventConsumerStub.run', 'del')], 1),
    # provider: sync run; gen plugin: sync run
    ([('EventConsumerStub.run', 'set'), ('GenericStub.run', 'set')], 3),
    # provider: no run; gen plugin: sync run
    ([('EventConsumerStub.run', 'del'), ('GenericStub.run', 'set')], 3),
    # provider: sync run; gen plugin: no run
    ([('EventConsumerStub.run', 'set'), ('GenericStub.run', 'del')], 3),
    # provider: no run; gen plugin: no run
    ([('EventConsumerStub.run', 'del'), ('GenericStub.run', 'del')], 3),
    # provider: async run; gen plugin: sync run
    ([('GenericStub.run', 'set')], 1),
    # provider: async run; gen plugin: no run
    ([('GenericStub.run', 'del')], 1),
    # confirm the same logic works for handle_message
    ([('EventConsumerStub.handle_message', 'set')], 1),
    ([('EventConsumerStub.handle_message', 'del')], 1),
))
def test_gather_plugins_by_type_logs(patches, exp_mock_call, monkeypatch,
                                     inited_plugins, mock_log_or_exit_on_exc):

    def _set_or_delete(patch, action):
        if action == 'del':
            monkeypatch.delattr(patch, raising=False)
        else:
            monkeypatch.setattr(patch, lambda: None)

    if patches:
        base_patch = 'tests.unit.conftest.'
        for patch, action in patches:
            patch = base_patch + patch
            _set_or_delete(patch, action)

    main._gather_plugins_by_type(inited_plugins.values(), debug=True)

    assert exp_mock_call == mock_log_or_exit_on_exc.call_count


@pytest.mark.parametrize('input_plugins,exp_mock_call,exp_plugin_count', [
    (['event_consumer'], 0, (1, 1)),
    (['event_consumer', 'publisher'], 0, (1, 2)),
    (['publisher'], 1, (0, 1)),
    (['runnable'], 1, (1, 0)),
])
def test_gather_plugins_by_type(input_plugins, exp_mock_call, exp_plugin_count,
                                inited_plugins, mock_log_or_exit_on_exc):
    plugins = [inited_plugins[i] for i in input_plugins]
    runnable_plugins, message_handlers = \
        main._gather_plugins_by_type(plugins, debug=True)
    assert exp_plugin_count == (len(runnable_plugins), len(message_handlers))
    assert exp_mock_call == mock_log_or_exit_on_exc.call_count


@pytest.mark.asyncio
async def test_run_plugins(inited_plugins, mocker, monkeypatch):
    """Run all installed plugins."""
    async def mock_run(*args, **kwargs):
        await asyncio.sleep(0)

    mock_router = mocker.Mock()
    monkeypatch.setattr(mock_router, 'run', mock_run)

    runnable_plugins, _ = main._gather_plugins_by_type(
        inited_plugins.values(), True)
    await main._run(runnable_plugins, mock_router, debug=True)

    assert 1 == inited_plugins['event_consumer']._mock_run_count
    assert 1 == inited_plugins['runnable']._mock_run_count


@pytest.fixture
def event_loop_mock(mocker, monkeypatch):
    mock = mocker.Mock()
    mock.return_value.add_signal_handler = mocker.Mock()
    monkeypatch.setattr('gordon.main.asyncio.get_event_loop', mock)
    return mock.return_value


@pytest.mark.parametrize('has_active_plugins,exp_log_count,errors', (
    (True, 2, []),
    (True, 2, [('not_a.plugin', conftest.plugin_exc_mock())]),
    (False, 1, []),
))
def test_run_cli(has_active_plugins, exp_log_count, errors, installed_plugins,
                 setup_mock, mock_plugins_loader, mocker, monkeypatch, caplog,
                 loaded_config, event_loop_mock):
    """Successfully run gordon service in debug mode via CLI."""
    loaded_config['core']['debug'] = True
    names, _plugins = [], []

    if has_active_plugins:
        names = [
            'event_consumer.plugin',
            'enricher.plugin',
            'publisher.plugin'
        ]
        _plugins = [
            conftest.EventConsumerStub({}, mocker.Mock(), mocker.Mock()),
            conftest.EnricherStub({}, None),
            conftest.PublisherStub({}, None)
        ]
    mock_plugins_loader.return_value = (
        names, _plugins, errors, {'metrics': mocker.Mock()})
    _run_mock = mocker.Mock()
    monkeypatch.setattr('gordon.main._run', _run_mock)
    _log_or_exit_mock = mocker.Mock()
    monkeypatch.setattr('gordon.main._log_or_exit_on_exceptions',
                        _log_or_exit_mock)
    _setup_router_mock = mocker.Mock()
    monkeypatch.setattr('gordon.main._setup_router', _setup_router_mock)

    runner = CliRunner()
    result = runner.invoke(main.run)

    assert 0 == result.exit_code
    setup_mock.assert_called_once()
    assert 3 == event_loop_mock.add_signal_handler.call_count
    event_loop_mock.create_task.assert_called_once_with(
        _run_mock(_plugins, True))
    event_loop_mock.run_forever.assert_called_once_with()
    event_loop_mock.close.assert_called_once()
    assert exp_log_count == len(caplog.records)
    if errors:
        _log_or_exit_mock.assert_called_once()


def test_run_cli_raise_exceptions(loaded_config, installed_plugins, caplog,
                                  setup_mock, mock_plugins_loader,
                                  plugin_exc_mock, mocker):
    """Raise plugin exceptions when not in debug mode via CLI."""
    loaded_config['core']['debug'] = False
    setup_mock.return_value = loaded_config

    names = ['event_consumer', 'enricher']
    errors = [('not_a_plugin', plugin_exc_mock)]
    mock_plugins_loader.return_value = names, installed_plugins, errors, \
        mocker.Mock()

    runner = CliRunner()
    result = runner.invoke(main.run)

    assert 1 == result.exit_code
    setup_mock.assert_called_once()
    assert 1 == len(caplog.records)
