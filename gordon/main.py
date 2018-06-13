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
Main module to run the Gordon service.

The service expects a ``gordon.toml`` and/or a ``gordon-user.toml``
file for configuration in the current working directory, or in a
provided root directory.

Any configuration defined in ``gordon-user.toml`` overwrites those in
``gordon.toml``.

Example:

.. code-block:: bash

    $ python gordon/main.py
    $ python gordon/main.py -c /etc/default/
    $ python gordon/main.py --config-root /etc/default/
"""

import asyncio
import logging
import os

import click
import toml
import ulogger

from gordon import __version__ as version
from gordon import exceptions
from gordon import interfaces
from gordon import plugins_loader
from gordon import router


def _load_config(root=''):
    conf, error = {}, False
    conf_files = ['gordon.toml', 'gordon-user.toml']
    for conf_file in conf_files:
        try:
            with open(os.path.join(root, conf_file), 'r') as f:
                conf.update(toml.load(f))
        except IOError:
            error = True

    if error and conf == {}:
        raise IOError(f'Cannot load Gordon configuration file from "{root}".')
    return conf


def setup(config_root=''):
    """
    Service configuration and logging setup.

    Configuration defined in ``gordon-user.toml`` will overwrite
    ``gordon.toml``.

    Args:
        config_root (str): Where configuration should load from,
            defaults to current working directory.
    Returns:
        A dict for Gordon service configuration.
    """
    config = _load_config(root=config_root)

    logging_config = config.get('core', {}).get('logging', {})
    log_level = logging_config.get('level', 'INFO').upper()
    log_handlers = logging_config.get('handlers') or ['syslog']

    ulogger.setup_logging(
        progname='gordon', level=log_level, handlers=log_handlers)

    return config


def _log_or_exit_on_exceptions(base_msg, exc, debug):
    log_level_func = logging.warn
    if not debug:
        log_level_func = logging.error

    if isinstance(exc, list):
        for exception in exc:
            log_level_func(base_msg, exc_info=exception)
    else:
        log_level_func(base_msg, exc_info=exc)

    if not debug:
        raise SystemExit(1)


def _assert_required_plugins(installed_plugins, debug):
    # enricher not required
    required_providers_available = {
        'event_consumer': False,
        'publisher': False,
    }
    for plugin in installed_plugins:
        if interfaces.IEventConsumerClient.providedBy(plugin):
            required_providers_available['event_consumer'] = True
        elif interfaces.IPublisherClient.providedBy(plugin):
            required_providers_available['publisher'] = True

    missing = []
    msg = ('The provider for the "{name}" interface is not configured for the '
           'Gordon service or is not implemented.')
    for provider, available in required_providers_available.items():
        if not available:
            exc = exceptions.MissingPluginError(msg.format(name=provider))
            missing.append(exc)
    if missing:
        base_msg = 'Problem running plugins: '
        _log_or_exit_on_exceptions(base_msg, missing, debug=debug)


def _gather_runnable_plugins(plugins, debug):
    plugins_to_run = []
    for plugin in plugins:
        if interfaces.IEventConsumerClient.providedBy(plugin):
            # TODO (lynn): this should be switched out for adding
            # the "verify interface implementation" ability. See
            # https://docs.zope.org/zope.interface/verify.html
            if not hasattr(plugin, 'run') or \
                    not asyncio.iscoroutinefunction(plugin.run):
                msg = (f'Implemention "{plugin}" of the required '
                       '"IEventConsumerClient" interface does not have the '
                       'necessary `run` method.')
                exc = exceptions.InvalidPluginError(msg)
                _log_or_exit_on_exceptions(msg, exc, debug)
                continue
            plugins_to_run.append(plugin)
        elif hasattr(plugin, 'run') and asyncio.iscoroutinefunction(plugin.run):
            plugins_to_run.append(plugin)

    return plugins_to_run


def _gather_implemented_providers(plugins):
    implemented = {}
    for plugin in plugins:
        if interfaces.IEventConsumerClient.providedBy(plugin):
            implemented['event_consumer'] = plugin
        elif interfaces.IEnricherClient.providedBy(plugin):
            implemented['enricher'] = plugin
        elif interfaces.IPublisherClient.providedBy(plugin):
            implemented['publisher'] = plugin
    return implemented


def _setup_message_router(plugins, success_channel, error_channel):
    implemented_plugins = _gather_implemented_providers(plugins)
    msg_router = router.GordonRouter(
        success_channel, error_channel, implemented_plugins)
    return msg_router


async def _run(plugins, msg_router, debug):
    _assert_required_plugins(plugins, debug)
    plugins_to_run = _gather_runnable_plugins(plugins, debug)
    tasks = [p.run() for p in plugins_to_run]
    tasks.append(msg_router.run())
    await asyncio.gather(*tasks)


@click.command()
@click.option('-c', '--config-root',
              type=click.Path(exists=True), required=False, default='.',
              help='Directory where to find service configuration.')
def run(config_root):
    config = setup(os.path.abspath(config_root))
    debug_mode = config.get('core', {}).get('debug', False)

    # TODO: initialize a metrics object - either here or within `load_plugins`
    channels = {
        'success_channel': asyncio.Queue(),
        'error_channel': asyncio.Queue(),
    }
    plugin_names, plugins, errors, metrics = plugins_loader.load_plugins(
        config, channels)
    if errors:
        for err_plugin, exc in errors:
            base_msg = 'Plugin was not loaded: {err_plugin}'
            _log_or_exit_on_exceptions(base_msg, exc, debug=debug_mode)

    if plugin_names:
        logging.info(f'Loaded {len(plugin_names)} plugins: {plugin_names}.')

    msg_router = _setup_message_router(plugins, **channels)

    logging.info(f'Starting gordon v{version}...')
    loop = asyncio.get_event_loop()
    try:
        loop.create_task(_run(plugins, msg_router, debug_mode))
        loop.run_forever()
    finally:
        loop.stop()


if __name__ == '__main__':
    run()
