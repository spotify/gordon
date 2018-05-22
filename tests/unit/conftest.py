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

import pkg_resources
import pytest
import zope.interface

from gordon import interfaces


@zope.interface.implementer(interfaces.IEventConsumerClient)
class EventConsumerStub:
    def __init__(self, config, success_chnl, error_chnl, **kwargs):
        self.config = config
        self.success_chnl = success_chnl
        self.error_chnl = error_chnl
        self._mock_run_count = 0

    async def run(self):
        await asyncio.sleep(0)
        self._mock_run_count += 1

    async def cleanup(self):
        pass

    async def shutdown(self):
        pass


@zope.interface.implementer(interfaces.IEnricherClient)
class EnricherStub:
    def __init__(self, config, success_chnl, error_chnl, **kwargs):
        self.config = config
        self.success_chnl = success_chnl
        self.error_chnl = error_chnl

    async def process(self):
        pass

    async def shutdown(self):
        pass


@zope.interface.implementer(interfaces.IPublisherClient)
class PublisherStub:
    def __init__(self, config, success_chnl, error_chnl, **kwargs):
        self.config = config
        self.success_chnl = success_chnl
        self.error_chnl = error_chnl

    async def publish_changes(self):
        pass

    async def shutdown(self):
        pass


class GenericStub:
    def __init__(self, config, success_chnl, error_chnl, **kwargs):
        self.config = config
        self.success_chnl = success_chnl
        self.error_chnl = error_chnl
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
    return ('[core]\n'
            'plugins = ["xyz.event_consumer", "xyz.enricher",'
            ' "xyz.publisher"]\n'
            'debug = true\n'
            '[core.logging]\n'
            'level = "debug"\n'
            'handlers = ["stream"]\n'
            '[xyz]\n'
            'a_key = "a_value"\n'
            'b_key = "b_value"\n'
            '[xyz.event_consumer]\n'
            'a_key = "another_value"\n'
            '[xyz.enricher]\n'
            'd_key = "d_value"\n'
            '[xyz.publisher]\n'
            'c_key = "c_value"')


@pytest.fixture
def loaded_config():
    return {
        'core': {
            'plugins': [
                'xyz.event_consumer', 'xyz.enricher', 'xyz.publisher'],
            'debug': True,
            'logging': {
                'level': 'debug',
                'handlers': ['stream'],
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
            },
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

    return {
        'xyz.event_consumer': mock_plugin('xyz.event_consumer'),
        'xyz.enricher': mock_plugin('xyz.enricher'),
        'xyz.publisher': mock_plugin('xyz.publisher'),
        'xyz.runnable': mock_plugin('xyz.runnable'),
    }


@pytest.fixture
def caplog(caplog):
    """Set global test logging levels."""
    caplog.set_level(logging.DEBUG)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    return caplog


@pytest.fixture(scope='session')
def plugin_kwargs():
    return {
        'success_chnl': asyncio.Queue(),
        'error_chnl': asyncio.Queue(),
    }


@pytest.fixture
def inited_plugins(plugin_kwargs):
    plugin_names = [
        'event_consumer', 'enricher', 'publisher', 'runnable'
    ]
    plugins = {}
    for name in plugin_names:
        conf = _get_plugin_conf(name)
        plugins[name] = _get_stub_class(name)(conf, **plugin_kwargs)

    return plugins
