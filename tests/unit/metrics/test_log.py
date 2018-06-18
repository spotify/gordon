# -*- coding: utf-8 -*-
# Copyright (c) 2018 Spotify AB
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

import numbers

import pytest

from gordon.metrics import log


@pytest.mark.parametrize('context,context_str', [
    ({'source': 'external'}, ' context: {\'source\': \'external\'}'),
    ({}, '')
])
def test_logger_adapter_log_outputs_message(caplog, context, context_str):
    """Metric is formatted and output to log."""
    logger_adapter = log.LoggerAdapter('INFO')
    metric = {
        'metric_name': 'events',
        'value': 12.12,
        'context': context
        }
    logger_adapter.log(metric)
    assert 1 == len(caplog.records)
    expected_log = '[events] value: 12.12' + context_str
    assert expected_log == caplog.records[0].msg


@pytest.fixture
def mock_logger_adapter(mocker):
    return mocker.Mock(log.LoggerAdapter)


@pytest.fixture
def log_timer(mock_logger_adapter):
    metric = {'metric_name': 'test-metric', 'value': 13.05, 'context': {}}
    return log.LogTimer(metric, mock_logger_adapter, 1)


@pytest.mark.asyncio
async def test_log_timer_manual(log_timer):
    """Times when using start/stop interface."""

    await log_timer.start()
    assert isinstance(log_timer._start_time, numbers.Number)

    await log_timer.stop()
    assert 1 == log_timer.logger.log.call_count
    actual_metric = log_timer.logger.log.mock_calls[0][1][0]
    assert 'test-metric' == actual_metric['metric_name']
    assert {} == actual_metric['context']
    assert 0 < actual_metric['value']


@pytest.mark.asyncio
async def test_log_timer_as_context_manager(log_timer):
    """Times when using as a context manager."""
    async with log_timer as t:
        assert isinstance(t._start_time, numbers.Number)
    actual_metric = log_timer.logger.log.mock_calls[0][1][0]
    assert 1 == log_timer.logger.log.call_count
    assert 'test-metric' == actual_metric['metric_name']
    assert {} == actual_metric['context']
    assert 0 < actual_metric['value']


@pytest.fixture
def relay_config():
    return {
        'time_unit': 1,
        'log_level': 'info',
    }


@pytest.mark.parametrize('name,val,context', [
    ('a-metric', 12, None),
    ('nother-metric', 0.0003, {'source': 'internal'}),
])
def test_logrelay_create_metric(relay_config, name, val, context):
    """Create a metric dictionary."""
    relay = log.LogRelay(relay_config)
    actual = relay._create_metric(name, val, context=context)

    expected = {
        'metric_name': name,
        'value': val,
        'context': context or {}
    }
    assert expected == actual


@pytest.fixture
def log_relay_inst(monkeypatch, mocker, relay_config):
    logger_mock = mocker.Mock(log.LoggerAdapter)
    monkeypatch.setattr(log, 'LoggerAdapter', logger_mock)
    return log.LogRelay(relay_config)


@pytest.mark.asyncio
@pytest.mark.parametrize('context', [
    {'source': 'perimiter'},
    None
])
async def test_logrelay_incr(log_relay_inst, context):
    """Initializes and outputs metrics to logger."""
    expected_metric = log_relay_inst._create_metric('requests-recv', 601,
                                                    context=context)
    await log_relay_inst.incr('requests-recv', 601, context=context)

    log_relay_inst.logger.log.assert_called_once_with(expected_metric)


@pytest.mark.asyncio
async def test_logrelay_incr_accumulation(mocker, log_relay_inst):
    """MetricRelay.incr accumulates values."""
    base_value = 441
    incr = 10
    expected_metric = log_relay_inst._create_metric('requests-recv',
                                                    base_value, context=None)
    expected_2nd_metric = log_relay_inst._create_metric(
        'requests-recv', base_value + incr, context=None)
    await log_relay_inst.incr('requests-recv', base_value)
    await log_relay_inst.incr('requests-recv', incr)

    assert base_value + incr == log_relay_inst.counters['requests-recv']
    expected_calls = [
        mocker.call(expected_metric),
        mocker.call(expected_2nd_metric)
    ]
    log_relay_inst.logger.log.assert_has_calls(expected_calls)


def test_logrelay_timer(log_relay_inst):
    """Initialize and return a LogTimer object."""
    expected_metric = log_relay_inst._create_metric('latency', None,
                                                    context=None)
    timer = log_relay_inst.timer('latency')
    assert isinstance(timer, log.LogTimer)
    assert expected_metric == timer.metric
    assert timer.logger == log_relay_inst.logger


@pytest.mark.asyncio
@pytest.mark.parametrize('context', [
    {'version': 'dev0'},
    None
])
async def test_logrelay_set(log_relay_inst, context):
    """Output single metric to logger."""
    expected_metric = log_relay_inst._create_metric('latency', 451,
                                                    context=context)
    await log_relay_inst.set('latency', 451, context=context)

    log_relay_inst.logger.log.assert_called_once_with(expected_metric)


@pytest.mark.asyncio
async def test_cleanup(log_relay_inst):
    """Implemented, but a noop."""
    assert await log_relay_inst.cleanup() is None
