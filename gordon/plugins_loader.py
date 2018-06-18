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
"""
Module for loading plugins distributed via third-party packages.

Plugin discovery is done via ``entry_points`` defined in a package's
``setup.py``, registered under ``'gordon.plugins'``. For example:

.. code-block:: python

    # setup.py
    from setuptools import setup

    setup(
        name=NAME,
        # snip
        entry_points={
            'gordon.plugins': [
                'gcp.gpubsub = gordon_gcp.gpubsub:EventClient',
                'gcp.gce.a = gordon_gcp.gce.a:ReferenceSourceClient',
                'gcp.gce.b = gordon_gcp.gce.b:ReferenceSourceClient',
                'gcp.gdns = gordon_gcp.gdns:DNSProviderClient',
            ],
        },
        # snip
    )

Plugins are initialized with any config defined in ``gordon-user.toml``
and ``gordon.toml``. See :doc:`config` for more details.

Once a plugin is found, the loader looks up its configuration via the
same key defined in its entry point, e.g. ``gcp.gpubsub``.

The value of the entry point (e.g. ``gordon_gcp.gpubsub:EventClient``)
must point to a class. The plugin class is instantiated with its config.

A plugin will not have access to another plugin's configuration. For
example, the ``gcp.gpusub`` will not have access to the configuration
for ``gcp.gdns``.

See :doc:`plugins` for details on how to write a plugin for Gordon.
"""

import logging

import pkg_resources

from gordon import exceptions
from gordon.metrics import ffwd
from gordon.metrics import log


PLUGIN_NAMESPACE = 'gordon.plugins'


def _init_plugins(active, installed, configs, kwargs):
    inited_plugins, inited_plugin_names, errors = [], [], []
    for plugin_name, unloaded_plugin in installed.items():
        if plugin_name not in active:
            continue
        plugin_class = unloaded_plugin.load()
        plugin_config = configs.get(plugin_name)

        # check against `None` because `plugin_config` could be `{}`,
        # which should be handled by the plugin's logic (i.e. accept all
        # defaults, or raise error, or something else)
        if plugin_config is None:
            msg = (f'Skipped loading plugin "{plugin_name}" because no '
                   'configuration was found.')
            logging.info(msg)
            continue

        try:
            plugin_object = plugin_class(plugin_config, **kwargs)
            inited_plugins.append(plugin_object)
            inited_plugin_names.append(plugin_name)
        except Exception as e:
            errors.append((plugin_name, e))

    return inited_plugin_names, inited_plugins, errors


def _merge_config(config, namespace):
    config_copy = config.copy()
    keys_to_merge = namespace.split('.')

    # DFS approach in order to prefer child config to parent config
    merged_plugin_config = {}
    while keys_to_merge:
        ns = '.'.join(keys_to_merge)
        plugin_config = config_copy.get(ns, {})
        plugin_config_copy = plugin_config.copy()
        plugin_config_copy.update(merged_plugin_config)
        merged_plugin_config = plugin_config_copy
        keys_to_merge.pop()
    return merged_plugin_config


def _get_namespaced_config(config, plugin_namespace, all_plugins):
    plugin_config_keys = plugin_namespace.split('.')

    # drill down to get config that matches plugin namespace
    while plugin_config_keys:
        key = plugin_config_keys.pop(0)
        config = config.get(key)

    # find which config namespaces map to other plugins
    plugin_config_keys_to_exclude = set()
    for plugin in all_plugins:
        if plugin == plugin_namespace:
            continue
        if plugin.startswith(plugin_namespace):
            # exclude same level & lower config keys for other plugins
            keys_to_exclude = plugin.lstrip(plugin_namespace).split('.')
            plugin_config_keys_to_exclude.update(keys_to_exclude)

    # clean up config by removing other plugin configs
    plugin_config = config.copy()
    while plugin_config_keys_to_exclude:
        key = plugin_config_keys_to_exclude.pop()
        try:
            plugin_config.pop(key)
        except KeyError:
            pass

    return plugin_namespace, plugin_config


def _load_plugin_configs(plugin_names, config):
    # A plugin should only have access to its own config and
    # parent/global plugin config, but not configs of other plugins
    plugin_configs = {}
    for plugin in plugin_names:
        namespace, plugin_conf = _get_namespaced_config(
            config, plugin, plugin_names)
        plugin_configs[namespace] = plugin_conf

    # merge namespaced with parent / global plugin config
    merged_configs = {}
    for namespace in plugin_configs.keys():
        plugin_config = _merge_config(plugin_configs, namespace)
        merged_configs[namespace] = plugin_config

    return merged_configs


def _get_plugin_config_keys(plugins):
    # Make sure all parent namespaces of a plugin are available
    # to load config for easy config handling
    all_config_keys = set()
    for namespace in plugins:
        namespaces = namespace.split('.')
        namespaces_to_build = []
        while len(namespaces):
            namespace = namespaces.pop(0)
            namespaces_to_build.append(namespace)
            config_key = '.'.join(namespaces_to_build)
            all_config_keys.add(config_key)
    return sorted(list(all_config_keys))


def _get_activated_plugins(config, installed_plugins):
    activated_plugins = config.get('core', {}).get('plugins', [])
    for active_plugin in activated_plugins:
        if active_plugin not in installed_plugins:
            msg = f'Plugin "{active_plugin}" not installed'
            raise exceptions.LoadPluginError(msg)
    return activated_plugins


def _gather_installed_plugins():
    gathered_plugins = {}
    for entry_point in pkg_resources.iter_entry_points(PLUGIN_NAMESPACE):
        gathered_plugins[entry_point.name] = entry_point
    return gathered_plugins


def _get_metrics_plugin(config, installed_plugins):
    metrics_provider = config.get('core', {}).get('metrics', 'metrics-logger')
    metrics_config = config.get(metrics_provider, {})

    if metrics_provider == 'metrics-logger':
        return log.LogRelay(metrics_config)

    if metrics_provider == 'ffwd':
        return ffwd.SimpleFfwdRelay(metrics_config)

    for plugin_name, plugin in installed_plugins.items():
        if metrics_provider == plugin_name:
            plugin_class = plugin.load()
            return plugin_class(metrics_config)

    msg = f'Metrics Plugin "{metrics_provider}" configured, but not installed'
    raise exceptions.LoadPluginError(msg)


def load_plugins(config, plugin_kwargs):
    """
    Discover and instantiate plugins.

    Args:
        config (dict): loaded configuration for the Gordon service.
        plugin_kwargs (dict): keyword arguments to give to plugins
            during instantiation.
    Returns:
        Tuple of 3 lists: list of names of plugins, list of
        instantiated plugin objects, and any errors encountered while
        loading/instantiating plugins. A tuple of three empty lists is
        returned if there are no plugins found or activated in gordon
        config.
    """
    installed_plugins = _gather_installed_plugins()
    metrics_plugin = _get_metrics_plugin(config, installed_plugins)
    if metrics_plugin:
        plugin_kwargs['metrics'] = metrics_plugin

    active_plugins = _get_activated_plugins(config, installed_plugins)
    if not active_plugins:
        return [], [], [], None
    plugin_namespaces = _get_plugin_config_keys(active_plugins)
    plugin_configs = _load_plugin_configs(plugin_namespaces, config)
    plugin_names, plugins, errors = _init_plugins(
        active_plugins, installed_plugins, plugin_configs, plugin_kwargs)
    return plugin_names, plugins, errors, plugin_kwargs
