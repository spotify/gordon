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

import pkg_resources
import pytest
import zope.interface

from gordon import exceptions
from gordon import interfaces
from gordon import plugins_loader
from gordon.metrics import ffwd
from tests.unit import conftest


#####
# Fixtures
#####
@pytest.fixture(scope='session')
def namespaced_config():
    return {
        'event_consumer': {'a_key': 'a_value', 'b_key': 'b_value'},
        'event_consumer.plugin': {'a_key': 'another_value'},
        'enricher': {},
        'enricher.plugin': {'d_key': 'd_value'}
    }


@pytest.fixture(scope='session')
def plugin_config():
    return {
        'xyz': {
            'a_key': 'a_value',
            'b_key': 'b_value',
        },
        'xyz.event_consumer': {
            'a_key': 'another_value',
            'b_key': 'b_value'
        },
        'xyz.enricher': {
            'a_key': 'a_value',
            'b_key': 'b_value',
            'd_key': 'd_value',
        },
        'xyz.publisher': {
            'a_key': 'a_value',
            'b_key': 'b_value',
            'c_key': 'c_value',
        }
    }


@pytest.fixture
def exp_inited_plugins(plugin_config, plugin_kwargs):
    return [
        conftest.EventConsumerStub(
            plugin_config['xyz.event_consumer'], **plugin_kwargs),
        conftest.EnricherStub(
            plugin_config['xyz.enricher'], **plugin_kwargs),
        conftest.PublisherStub(
            plugin_config['xyz.publisher'], **plugin_kwargs)
    ]


@pytest.fixture
def mock_iter_entry_points(mocker, monkeypatch, installed_plugins):
    mock_plugins = installed_plugins.values()

    mock_iter_entry_points = mocker.MagicMock(pkg_resources.iter_entry_points)
    mock_iter_entry_points.return_value = iter(mock_plugins)
    monkeypatch.setattr(plugins_loader.pkg_resources, 'iter_entry_points',
                        mock_iter_entry_points)


def is_instance_of_stub(obj):
    stubs = [
        conftest.EventConsumerStub,
        conftest.EnricherStub,
        conftest.PublisherStub,
        conftest.GenericStub
    ]
    return any([isinstance(obj, stub) for stub in stubs])


#####
# The good stuff
#####
def test_init_plugins(installed_plugins, plugin_config, inited_plugins,
                      plugin_kwargs):
    """Plugins are initialized with their config."""
    inited_names, inited_plugins, errors = plugins_loader._init_plugins(
        conftest.REGISTERED_ACTIVE_PLUGINS, installed_plugins, plugin_config,
        plugin_kwargs
    )

    assert sorted(conftest.REGISTERED_ACTIVE_PLUGINS) == sorted(inited_names)
    for plugin_obj in inited_plugins:
        assert is_instance_of_stub(plugin_obj)
        assert any([p.config == plugin_obj.config for p in inited_plugins])


def test_init_plugins_exceptions(mocker, plugin_kwargs):
    """Non-callable plugin returns plugin-specific exceptions."""
    name = 'B0rkedPlugin'
    config = {'B0rkedPlugin': {'foo': 'bar'}}

    plugin_mock = mocker.MagicMock(pkg_resources.EntryPoint, autospec=True)
    plugin_mock.name = name
    plugin_mock.load.return_value = 'not_a_class'
    plugins = {name: plugin_mock}

    inited_names, inited_plugins, errors = plugins_loader._init_plugins(
        [name], plugins, config, plugin_kwargs)
    assert 1 == len(errors)


def test_init_plugins_skipped(installed_plugins, plugin_config, caplog,
                              plugin_kwargs):
    """Skips plugins that are not configured."""
    config = {'xyz.event_consumer': plugin_config['xyz.event_consumer']}

    inited_names, inited_plugins, errors = plugins_loader._init_plugins(
        conftest.REGISTERED_ACTIVE_PLUGINS, installed_plugins, config,
        plugin_kwargs
    )

    assert 1 == len(inited_plugins) == len(inited_names)
    assert 2 == len(caplog.records)


def test_init_plugins_empty_config(installed_plugins, plugin_kwargs):
    """Loads plugin if mathcing config key exists with empty config."""
    config = {name: {} for name in conftest.REGISTERED_ACTIVE_PLUGINS}

    inited_names, inited_plugins, errors = plugins_loader._init_plugins(
        conftest.REGISTERED_ACTIVE_PLUGINS, installed_plugins, config,
        plugin_kwargs
    )

    assert 3 == len(inited_plugins) == len(inited_names)
    for plugin_obj in inited_plugins:
        assert {} == plugin_obj.config


def test_init_plugins_skip_inactive(installed_plugins, plugin_config,
                                    plugin_kwargs):
    """Skips plugins that are not activated in core config."""
    inited_names, inited_plugins, errors = plugins_loader._init_plugins(
        [conftest.REGISTERED_ACTIVE_PLUGINS[0]], installed_plugins,
        plugin_config, plugin_kwargs)

    assert 1 == len(inited_plugins) == len(inited_names)
    exp = plugin_config.get(conftest.REGISTERED_ACTIVE_PLUGINS[0])
    assert exp == inited_plugins[0].config


@pytest.mark.parametrize('namespace,exp_config', (
    ('event_consumer', {'a_key': 'a_value', 'b_key': 'b_value'}),
    ('event_consumer.plugin', {'a_key': 'another_value', 'b_key': 'b_value'}),
    ('enricher', {}),
    ('enricher.plugin', {'d_key': 'd_value'})
))
def test_merge_config(namespace, exp_config, namespaced_config):
    """Namespaced config for a plugin also has parent/global config."""
    ret_config = plugins_loader._merge_config(namespaced_config, namespace)

    assert exp_config == ret_config


@pytest.mark.parametrize('namespace,exp_config', (
    ('xyz', {'a_key': 'a_value', 'b_key': 'b_value'}),
    ('xyz.event_consumer', {'a_key': 'another_value'}),
    ('xyz.enricher', {'d_key': 'd_value'}),
))
def test_get_namespaced_config(namespace, exp_config, installed_plugins,
                               loaded_config):
    """Tease out config specific to a plugin with no parent config."""
    all_plugins = installed_plugins.keys()
    ret_namespace, ret_config = plugins_loader._get_namespaced_config(
        loaded_config, namespace, all_plugins)

    assert exp_config == ret_config
    assert namespace == ret_namespace


def test_load_plugin_configs(installed_plugins, loaded_config, plugin_config):
    """Load plugin-specific config ignoring other plugins' configs."""
    plugin_names = ['xyz'] + conftest.REGISTERED_ACTIVE_PLUGINS
    parsed_config = plugins_loader._load_plugin_configs(
        plugin_names, loaded_config)

    for name in conftest.REGISTERED_ACTIVE_PLUGINS:
        assert plugin_config[name] == parsed_config[name]


def test_get_plugin_config_keys(installed_plugins):
    """Entry point keys for plugins are parsed to config keys."""
    config_keys = plugins_loader._get_plugin_config_keys(installed_plugins)
    expected = ['xyz'] + conftest.REGISTERED_PLUGINS
    assert sorted(expected) == sorted(config_keys)


def test_get_activated_plugins(loaded_config, installed_plugins):
    """Assert activated plugins are installed."""
    active = plugins_loader._get_activated_plugins(
        loaded_config, installed_plugins)

    assert conftest.REGISTERED_ACTIVE_PLUGINS == active


def test_get_activated_plugins_raises(loaded_config, installed_plugins):
    """Raise when activated plugins are not installed."""
    loaded_config['core']['plugins'].append('xyz.not_installed_plugin')

    with pytest.raises(exceptions.LoadPluginError) as e:
        plugins_loader._get_activated_plugins(loaded_config, installed_plugins)

    e.match('Plugin "xyz.not_installed_plugin" not installed')


def test_gather_installed_plugins(mock_iter_entry_points, installed_plugins):
    """Gather entry points/plugins into a {name: entry point} format."""
    gathered_plugins = plugins_loader._gather_installed_plugins()
    assert sorted(installed_plugins) == sorted(gathered_plugins)


def test_load_plugins(mock_iter_entry_points, loaded_config, installed_plugins,
                      exp_inited_plugins, plugin_kwargs):
    """Plugins are loaded and instantiated with their config."""
    inited_names, installed_plugins, errors, _ = plugins_loader.load_plugins(
        loaded_config, plugin_kwargs)

    assert 3 == len(inited_names) == len(installed_plugins)
    for plugin_obj in installed_plugins:
        assert is_instance_of_stub(plugin_obj)
        assert any([p.config == plugin_obj.config for p in exp_inited_plugins])


def test_load_plugins_none_loaded(mocker, installed_plugins, plugin_kwargs):
    """Return empty list when no plugins are found."""
    mock_iter_entry_points = mocker.MagicMock(pkg_resources.iter_entry_points)
    mock_iter_entry_points.return_value = []

    loaded_config = {'core': {}}

    inited_names, installed_plugins, errors, _ = plugins_loader.load_plugins(
        loaded_config, plugin_kwargs)
    assert [] == installed_plugins == inited_names == errors


def test_load_plugins_exceptions(installed_plugins, loaded_config,
                                 mock_iter_entry_points, plugin_exc_mock,
                                 plugin_kwargs, mocker, monkeypatch):
    """Loading plugin exceptions are returned."""
    inited_plugins_mock = mocker.MagicMock(
        plugins_loader._init_plugins, autospec=True)

    exc = [('bad.plugin', plugin_exc_mock)]
    inited_plugins_mock.return_value = (
        conftest.REGISTERED_PLUGINS, inited_plugins_mock, exc)
    monkeypatch.setattr(plugins_loader, '_init_plugins', inited_plugins_mock)

    inited_names, installed_plugins, errors, _ = plugins_loader.load_plugins(
        loaded_config, plugin_kwargs)
    assert 1 == len(errors)


@zope.interface.implementer(interfaces.IMetricRelay)
class MetricRelayStub:
    def __init__(self, config):
        pass


@pytest.fixture
def metrics_mock(mocker):
    relay_mock = mocker.MagicMock(pkg_resources.EntryPoint)
    relay_mock.name = 'mock-provider-name'
    relay_mock.load.return_value = MetricRelayStub
    return relay_mock


@pytest.fixture
def plugins_incl_metrics(mocker, monkeypatch, metrics_mock, installed_plugins):
    installed_plugins[metrics_mock.name] = metrics_mock
    mock_iter_entry_points = mocker.Mock(pkg_resources.iter_entry_points)
    mock_iter_entry_points.return_value = iter(installed_plugins.values())
    monkeypatch.setattr(plugins_loader.pkg_resources, 'iter_entry_points',
                        mock_iter_entry_points)
    return installed_plugins


def test_load_plugins_with_metrics(plugins_incl_metrics, loaded_config,
                                   exp_inited_plugins, plugin_kwargs,
                                   metrics_mock):
    """Plugins are loaded and instantiated with their config and metrics."""
    loaded_config['core'].update({'metrics': metrics_mock.name})
    names, installed_plugins, errors, plugin_kw = plugins_loader.load_plugins(
        loaded_config, plugin_kwargs)

    # if metrics were included, len() would be 4
    assert 3 == len(names) == len(installed_plugins)
    for plugin_obj in installed_plugins:
        assert not isinstance(plugin_obj, MetricRelayStub)
        assert is_instance_of_stub(plugin_obj)
        assert any([p.config == plugin_obj.config for p in exp_inited_plugins])
        assert isinstance(plugin_kw['metrics'], MetricRelayStub)


def test_get_metrics_returns_ffwd(loaded_config, plugins_incl_metrics):
    loaded_config['core'].update({'metrics': 'ffwd'})
    actual = plugins_loader._get_metrics_plugin(
        loaded_config, plugins_incl_metrics)
    assert isinstance(actual, ffwd.SimpleFfwdRelay)


def test_get_metrics_returns_plugin(metrics_mock, plugins_incl_metrics):
    """MetricRelay should load if both implements interface and configured."""
    config = {'core': {'metrics': 'mock-provider-name'}}
    actual = plugins_loader._get_metrics_plugin(config, plugins_incl_metrics)
    assert isinstance(actual, MetricRelayStub)


def test_get_metrics_not_installed_raises(installed_plugins):
    """Return None if config or name incorrect."""
    config = {'core': {'metrics': 'non-installed-metrics-provider'}}
    with pytest.raises(exceptions.LoadPluginError) as e:
        plugins_loader._get_metrics_plugin(config, installed_plugins)

    assert e.match('Metrics.*non-installed-metrics-provider.*not installed')
