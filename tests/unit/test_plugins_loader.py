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

from gordon import exceptions
from gordon import plugins_loader
from tests.unit.conftest import FakePlugin


#####
# Fixtures
#####
@pytest.fixture(scope='session')
def namespaced_config():
    return {
        'one': {'a_key': 'a_value', 'b_key': 'b_value'},
        'one.plugin': {'a_key': 'another_value'},
        'two': {},
        'two.plugin': {'d_key': 'd_value'}
    }


@pytest.fixture(scope='session')
def plugin_config():
    return {
        'one.plugin': {
            'a_key': 'another_value',
            'b_key': 'b_value'
        },
        'two.plugin': {
            'd_key': 'd_value'
        },
    }


@pytest.fixture(scope='session')
def exp_inited_plugins(plugin_config):
    return [
        FakePlugin(plugin_config.get('one.plugin')),
        FakePlugin(plugin_config.get('two.plugin'))
    ]


@pytest.fixture
def mock_iter_entry_points(mocker, monkeypatch, plugins):
    mock_plugins = plugins.values()

    mock_iter_entry_points = mocker.MagicMock(pkg_resources.iter_entry_points)
    mock_iter_entry_points.return_value = iter(mock_plugins)
    monkeypatch.setattr(
        plugins_loader.pkg_resources, 'iter_entry_points',
        mock_iter_entry_points)


#####
# The good stuff
#####
def test_init_plugins(plugins, plugin_config, exp_inited_plugins):
    """Plugins are initialized with their config."""
    active_plugins = ['one.plugin', 'two.plugin']
    inited_names, inited_plugins, errors = plugins_loader._init_plugins(
        active_plugins, plugins, plugin_config)

    assert active_plugins == sorted(inited_names)
    for plugin_obj in inited_plugins:
        assert isinstance(plugin_obj, FakePlugin)
        assert any([p.config == plugin_obj.config for p in exp_inited_plugins])


def test_init_plugins_exceptions(mocker):
    """Non-callable plugin returns plugin-specific exceptions."""
    name = 'B0rkedPlugin'
    config = {'B0rkedPlugin': {'foo': 'bar'}}

    plugin_mock = mocker.MagicMock(pkg_resources.EntryPoint, autospec=True)
    plugin_mock.name = name
    plugin_mock.load.return_value = 'not_a_class'
    plugins = {name: plugin_mock}

    inited_names, inited_plugins, errors = plugins_loader._init_plugins(
        [name], plugins, config)
    assert 1 == len(errors)


def test_init_plugins_skipped(plugins, plugin_config, caplog):
    """Skips plugins that are not configured."""
    active_plugins = ['one.plugin', 'two.plugin']
    config = {'one.plugin': plugin_config['one.plugin']}

    inited_names, inited_plugins, errors = plugins_loader._init_plugins(
        active_plugins, plugins, config)

    assert 1 == len(inited_plugins) == len(inited_names)
    assert 1 == len(caplog.records)


def test_init_plugins_empty_config(plugins):
    """Loads plugin if mathcing config key exists with empty config."""
    active_plugins = ['one.plugin', 'two.plugin']
    config = {
        'one.plugin': {},
        'two.plugin': {}
    }

    inited_names, inited_plugins, errors = plugins_loader._init_plugins(
        active_plugins, plugins, config)

    assert 2 == len(inited_plugins) == len(inited_names)
    for plugin_obj in inited_plugins:
        # assert isinstance(plugin_obj, FakePlugin)
        assert {} == plugin_obj.config


def test_init_plugins_skip_inactive(plugins, plugin_config):
    """Skips plugins that are not activated in core config."""
    active_plugins = ['one.plugin']
    inited_names, inited_plugins, errors = plugins_loader._init_plugins(
        active_plugins, plugins, plugin_config)

    assert 1 == len(inited_plugins) == len(inited_names)
    assert plugin_config.get('one.plugin') == inited_plugins[0].config


merge_args = 'namespace,exp_config'
merge_params = [
    ('one', {'a_key': 'a_value', 'b_key': 'b_value'}),
    ('one.plugin', {'a_key': 'another_value', 'b_key': 'b_value'}),
    ('two', {}),
    ('two.plugin', {'d_key': 'd_value'}),
]


@pytest.mark.parametrize(merge_args, merge_params)
def test_merge_config(namespace, exp_config, namespaced_config):
    """Namespaced config for a plugin also has parent/global config."""
    ret_config = plugins_loader._merge_config(namespaced_config, namespace)

    assert exp_config == ret_config


namespace_args = 'namespace,exp_config'
namespace_params = [
    ('one', {'a_key': 'a_value', 'b_key': 'b_value'}),
    ('one.plugin', {'a_key': 'another_value'}),
    ('two', {}),
    ('two.plugin', {'d_key': 'd_value'}),
]


@pytest.mark.parametrize(namespace_args, namespace_params)
def test_get_namespaced_config(namespace, exp_config, plugins, loaded_config):
    """Tease out config specific to a plugin with no parent config."""
    all_plugins = plugins.keys()
    ret_namespace, ret_config = plugins_loader._get_namespaced_config(
        loaded_config, namespace, all_plugins)

    assert exp_config == ret_config
    assert namespace == ret_namespace


def test_load_plugin_configs(plugins, loaded_config, plugin_config):
    """Load plugin-specific config ignoring other plugins' configs."""
    plugin_names = ['one', 'one.plugin', 'two', 'two.plugin']
    parsed_config = plugins_loader._load_plugin_configs(
        plugin_names, loaded_config)
    assert plugin_config['one.plugin'] == parsed_config['one.plugin']
    assert plugin_config['two.plugin'] == parsed_config['two.plugin']


def test_get_plugin_config_keys(plugins):
    """Entry point keys for plugins are parsed to config keys."""
    config_keys = plugins_loader._get_plugin_config_keys(plugins)
    expected = ['one', 'one.plugin', 'two', 'two.plugin']
    assert expected == config_keys


def test_get_activated_plugins(loaded_config, plugins):
    """Assert activated plugins are installed."""
    active = plugins_loader._get_activated_plugins(loaded_config, plugins)

    assert ['one.plugin', 'two.plugin'] == active


def test_get_activated_plugins_raises(loaded_config, plugins):
    """Raise when activated plugins are not installed."""
    loaded_config['core']['plugins'].append('three.plugin')

    with pytest.raises(exceptions.LoadPluginError) as e:
        plugins_loader._get_activated_plugins(loaded_config, plugins)

    e.match('Plugin "three.plugin" not installed')


def test_gather_installed_plugins(mock_iter_entry_points, plugins):
    """Gather entry points/plugins into a {name: entry point} format."""
    gathered_plugins = plugins_loader._gather_installed_plugins()
    assert plugins == gathered_plugins


def test_load_plugins(mock_iter_entry_points, loaded_config, plugins,
                      exp_inited_plugins):
    """Plugins are loaded and instantiated with their config."""
    inited_names, loaded_plugins, errors = plugins_loader.load_plugins(
        loaded_config)

    assert 2 == len(inited_names) == len(loaded_plugins)
    for plugin_obj in loaded_plugins:
        assert isinstance(plugin_obj, FakePlugin)
        assert any([p.config == plugin_obj.config for p in exp_inited_plugins])


def test_load_plugins_none_loaded(mocker, plugins, exp_inited_plugins):
    """Return empty list when no plugins are found."""
    mock_iter_entry_points = mocker.MagicMock(pkg_resources.iter_entry_points)
    mock_iter_entry_points.return_value = []

    loaded_config = {'core': {}}
    inited_names, loaded_plugins, errors = plugins_loader.load_plugins(
        loaded_config)
    assert [] == loaded_plugins == inited_names == errors


def test_load_plugins_exceptions(plugins, exp_inited_plugins, loaded_config,
                                 mock_iter_entry_points, plugin_exc_mock,
                                 mocker, monkeypatch):
    """Loading plugin exceptions are returned."""
    names = ['one.plugin', 'two.plugin']
    inited_plugins_mock = mocker.MagicMock(
        plugins_loader._init_plugins, autospec=True)

    exc = [('bad.plugin', plugin_exc_mock)]
    inited_plugins_mock.return_value = names, inited_plugins_mock, exc
    monkeypatch.setattr(plugins_loader, '_init_plugins', inited_plugins_mock)

    inited_names, loaded_plugins, errors = plugins_loader.load_plugins(
        loaded_config)
    assert 1 == len(errors)
