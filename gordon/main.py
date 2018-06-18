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
import signal

import click
import toml
import ulogger

from gordon import __version__ as version
from gordon import exceptions
from gordon import interfaces
from gordon import plugins_loader
from gordon import router


async def shutdown(sig, loop):
    """Gracefully cancel current tasks when app receives a shutdown signal."""
    logging.info(f'Received exit signal {sig.name}...')
    tasks = [task for task in asyncio.Task.all_tasks() if task is not
             asyncio.tasks.Task.current_task()]

    for task in tasks:
        logging.debug(f'Cancelling task: {task}')
        task.cancel()

    results = await asyncio.gather(*tasks, return_exceptions=True)
    logging.debug(f'Done awaiting cancelled tasks, results: {results}')

    loop.stop()
    logging.info('Shutdown complete.')


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


def _gather_plugins_by_type(plugins, debug):
    runnable_plugins = []
    message_handling_plugins = []
    for plugin in plugins:
        # TODO (lynn): these should be switched out for adding
        # the "verify interface implementation" ability. See
        # https://docs.zope.org/zope.interface/verify.html
        if interfaces.IRunnable.providedBy(plugin):
            if not hasattr(plugin, 'run') or \
                    not asyncio.iscoroutinefunction(plugin.run):
                msg = (f'Implemention "{plugin}" of the required '
                       '"IRunnable" interface does not have the '
                       'necessary `run` method.')
                exc = exceptions.InvalidPluginError(msg)
                _log_or_exit_on_exceptions(msg, exc, debug)
                continue
            runnable_plugins.append(plugin)

        if interfaces.IMessageHandler.providedBy(plugin):
            if not hasattr(plugin, 'handle_message') or \
                    not asyncio.iscoroutinefunction(plugin.handle_message):
                msg = (f'Implemention "{plugin}" of the required '
                       '"IMessageHandler" interface does not have the '
                       'necessary `handle_message` method.')
                exc = exceptions.InvalidPluginError(msg)
                _log_or_exit_on_exceptions(msg, exc, debug)
                continue
            message_handling_plugins.append(plugin)

    if not runnable_plugins or not message_handling_plugins:
        msg = (f'At least one runnable plugin is required.')
        exc = exceptions.MissingPluginError(msg)
        _log_or_exit_on_exceptions(msg, [exc], debug=debug)

    return runnable_plugins, message_handling_plugins


def _setup_router(config, plugins, metrics, success_channel, error_channel):
    msg_router = router.GordonRouter(
        config, success_channel, error_channel, plugins, metrics)
    return msg_router


async def _run(runnable_plugins, msg_router, debug):
    tasks = [p.run() for p in runnable_plugins]
    tasks.append(msg_router.run())
    await asyncio.gather(*tasks)


@click.command()
@click.option('-c', '--config-root',
              type=click.Path(exists=True), required=False, default='.',
              help='Directory where to find service configuration.')
def run(config_root):
    config = setup(os.path.abspath(config_root))
    debug_mode = config.get('core', {}).get('debug', False)

    plugin_kwargs = {
        'success_channel': asyncio.Queue(),
        'error_channel': asyncio.Queue(),
    }
    plugin_names, plugins, errors, plugin_kwargs = plugins_loader.load_plugins(
        config, plugin_kwargs)
    if errors:
        for err_plugin, exc in errors:
            base_msg = 'Plugin was not loaded: {err_plugin}'
            _log_or_exit_on_exceptions(base_msg, exc, debug=debug_mode)

    if plugin_names:
        logging.info(f'Loaded {len(plugin_names)} plugins: {plugin_names}.')

    runnables, message_handlers = _gather_plugins_by_type(plugins, debug_mode)

    route_config = config.get('core', {}).get('route', {})
    msg_router = _setup_router(
        route_config, message_handlers, **plugin_kwargs)

    logging.info(f'Starting gordon v{version}...')
    loop = asyncio.get_event_loop()

    # Register shutdown to signals

    for signame in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            signame, lambda: asyncio.ensure_future(shutdown(signame, loop)))

    try:
        loop.create_task(_run(runnables, msg_router, debug_mode))
        loop.run_forever()

    finally:
        loop.close()


if __name__ == '__main__':
    run()
