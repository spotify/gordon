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

import pkg_resources
import pytest


class FakePlugin:
    def __init__(self, config):
        self.config = config


@pytest.fixture
def plugin_exc_mock():
    class FakePluginException(Exception):
        """Exception raised from a plugin when loading"""
        pass
    return FakePluginException('dangit')


@pytest.fixture(scope='session')
def config_file():
    return ('[core]\n'
            'plugins = ["one.plugin", "two.plugin"]\n'
            'debug = true\n'
            '[core.logging]\n'
            'level = "debug"\n'
            'handlers = ["stream"]\n'
            '[one]\n'
            'a_key = "a_value"\n'
            'b_key = "b_value"\n'
            '[one.plugin]\n'
            'a_key = "another_value"\n'
            '[two.plugin]\n'
            'd_key = "d_value"')


@pytest.fixture
def loaded_config():
    return {
        'core': {
            'plugins': ['one.plugin', 'two.plugin'],
            'debug': True,
            'logging': {
                'level': 'debug',
                'handlers': ['stream'],
            }
        },
        'one': {
            'a_key': 'a_value',
            'b_key': 'b_value',
            'plugin': {
                'a_key': 'another_value',
            },
        },
        'two': {
            'plugin': {
                'd_key': 'd_value',
            },
        },
    }


@pytest.fixture
def plugins(mocker):
    plugins = {}
    names = ['one.plugin', 'two.plugin']
    for name in names:
        plugin_mock = mocker.MagicMock(pkg_resources.EntryPoint, autospec=True)
        plugin_mock.name = name
        plugin_mock.load.return_value = FakePlugin
        plugins[name] = plugin_mock
    return plugins
