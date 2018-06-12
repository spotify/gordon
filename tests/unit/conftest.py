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
Module for reusable pytest fixtures.
"""

import asyncio
import logging
import os

import pkg_resources
import pytest
import zope.interface

from gordon import interfaces


PLUGIN_NAMES = [
    'event_consumer',
    'enricher',
    'publisher',
    'runnable'
]
# what plugins are registered as within `setup.py:setup.entry_points`
REGISTERED_PLUGINS = ['xyz.' + p for p in PLUGIN_NAMES]
ACTIVE_NAMES = PLUGIN_NAMES[:3]
REGISTERED_ACTIVE_PLUGINS = REGISTERED_PLUGINS[:3]


@zope.interface.implementer(interfaces.IRunnable, interfaces.IMessageHandler)
class EventConsumerStub:
    start_phase = 'consume'
    phase = 'cleanup'

    def __init__(self, config, success_channel, error_channel, metrics=None,
                 **kwargs):
        self.config = config
        self.success_channel = success_channel
        self.error_channel = error_channel
        self._mock_run_count = 0
        self._mock_handle_message_count = 0

    async def handle_message(self, event_msg):
        await asyncio.sleep(0)
        self._mock_handle_message_count += 1

    async def run(self):
        await asyncio.sleep(0)
        self._mock_run_count += 1

    async def shutdown(self):
        pass


@zope.interface.implementer(interfaces.IMessageHandler)
class EnricherStub:
    phase = 'enrich'

    def __init__(self, config, metrics=None, **kwargs):
        self.config = config
        self._mock_handle_message_count = 0

    async def handle_message(self, event_msg):
        await asyncio.sleep(0)
        self._mock_handle_message_count += 1

    async def shutdown(self):
        pass


class PublisherStub(EnricherStub):
    phase = 'publish'


@zope.interface.implementer(interfaces.IRunnable)
class GenericStub:
    def __init__(self, config, success_channel, error_channel, metrics=None):
        self.config = config
        self.success_channel = success_channel
        self.error_channel = error_channel
        self._mock_run_count = 0

    async def run(self):
        await asyncio.sleep(0)
        self._mock_run_count += 1

    async def shutdown(self):
        pass


@pytest.fixture
def plugin_exc_mock():
    class FakePluginException(Exception):
        """Exception raised from a plugin when loading"""
        pass
    return FakePluginException('dangit')


@pytest.fixture(scope='session')
def config_file():
    here = os.path.dirname(os.path.realpath(__file__))
    filepath = os.path.join(here, 'fixtures/test-gordon.toml')
    with open(filepath, 'r') as f:
        return f.read()


@pytest.fixture
def loaded_config():
    return {
        'core': {
            'plugins': [
                'xyz.event_consumer',
                'xyz.enricher',
                'xyz.publisher'],
            'debug': True,
            'logging': {
                'level': 'debug',
                'handlers': ['stream'],
            },
            'route': {
                'consume': 'enrich',
                'enrich': 'publish',
                'publish': 'cleanup'
            }
        },
        'xyz': {
            'a_key': 'a_value',
            'b_key': 'b_value',
            'event_consumer': {
                'a_key': 'another_value',
            },
            'enricher': {
                'd_key': 'd_value',
            },
            'publisher': {
                'c_key': 'c_value',
            }
        }
    }


def _get_stub_class(plugin_name):
    plugin_name = plugin_name.split('.')[-1]
    return {
        'event_consumer': EventConsumerStub,
        'enricher': EnricherStub,
        'publisher': PublisherStub,
        'runnable': GenericStub
    }[plugin_name]


def _get_plugin_conf(plugin_name):
    conf = loaded_config()
    try:
        return conf[plugin_name]
    except KeyError:
        return {}


@pytest.fixture
def installed_plugins(mocker):
    def mock_plugin(name):
        plugin_mock = mocker.MagicMock(pkg_resources.EntryPoint)
        plugin_mock.name = name
        plugin_mock.load.return_value = _get_stub_class(name)
        return plugin_mock

    installed = {}
    for plugin_name in REGISTERED_PLUGINS:
        installed[plugin_name] = mock_plugin(plugin_name)
    return installed


@pytest.fixture
def caplog(caplog):
    """Set global test logging levels."""
    caplog.set_level(logging.DEBUG)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    return caplog


@pytest.fixture
def plugin_kwargs(event_loop):
    return {
        'success_channel': asyncio.Queue(),
        'error_channel': asyncio.Queue(),
    }


@pytest.fixture
def inited_plugins(plugin_kwargs):
    plugins = {}
    for name in PLUGIN_NAMES:
        conf = _get_plugin_conf(name)
        plugins[name] = _get_stub_class(name)(conf, **plugin_kwargs)

    return plugins
