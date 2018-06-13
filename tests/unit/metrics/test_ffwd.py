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

from gordon.metrics import ffwd


def test_ffwd_protocol_connection_made(mocker):
    """Message sends and connection closes."""
    mock_transport = mocker.Mock()
    message = 'Testing message!'

    protocol = ffwd.UDPClientProtocol(message)
    protocol.connection_made(mock_transport)

    mock_transport.sendto.assert_called_once_with(message)
    mock_transport.close.assert_called_once_with()


@pytest.mark.asyncio
async def test_udp_client_send(mocker):
    """Sends serialized metric using FfwdClientProtocol."""
    mock_loop = mocker.Mock()

    actual_func = None
    actual_addr = None

    async def mock_create_datagram_endpoint(func, remote_addr):
        nonlocal actual_func
        nonlocal actual_addr
        actual_func = func
        actual_addr = remote_addr

    mock_loop.create_datagram_endpoint = mock_create_datagram_endpoint

    udp_client = ffwd.UDPClient('1.2.3.4', '5678', mock_loop)
    await udp_client.send({'an': 'object'})

    actual_protocol = actual_func()
    assert isinstance(actual_protocol, ffwd.UDPClientProtocol)
    assert ('1.2.3.4', '5678') == actual_addr
    assert b'{"an": "object"}' == actual_protocol.message


@pytest.fixture
def mock_udp_client_and_metrics_sent(mocker):
    metrics_sent = []

    async def mock_send(metric):
        nonlocal metrics_sent
        metrics_sent.append(metric)

    mock_udp_client = mocker.Mock()
    mock_udp_client.send = mock_send
    return mock_udp_client, metrics_sent


@pytest.fixture
def timer_and_metrics_sent(mock_udp_client_and_metrics_sent):
    mock_udp_client, metrics_sent = mock_udp_client_and_metrics_sent
    metric = {'a': 'metric', 'value': None}
    timer = ffwd.FfwdTimer(metric, mock_udp_client)
    return timer, metrics_sent


@pytest.mark.asyncio
async def test_ffwdtimer_manual(timer_and_metrics_sent):
    """Times when operated manually."""
    timer, metrics_sent = timer_and_metrics_sent
    await timer.start()
    assert isinstance(timer._start_time, numbers.Number)

    await timer.stop()
    assert 1 == len(metrics_sent)
    assert 'metric' == metrics_sent[0]['a']
    assert 0 < metrics_sent[0]['value']


@pytest.mark.asyncio
async def test_ffwdtimer_as_context_manager(timer_and_metrics_sent):
    """Times as a context manager."""
    timer, metrics_sent = timer_and_metrics_sent
    async with timer as t:
        assert isinstance(t._start_time, numbers.Number)

    assert 1 == len(metrics_sent)
    assert 'metric' == metrics_sent[0]['a']
    assert 0 < metrics_sent[0]['value']


@pytest.fixture
def test_config():
    return {
        'key': 'service-name',
        'ffwd_ip': '1.2.3.4',
        'ffwd_port': '5678',
        'time_unit': 1E9
    }


TEST_KEY_NAME_VAL = [
    ('service-name', 'metric-name', 10),
    ('other-name', 'metric-name', 6.243289),
    ('service-name', 'other-metric', 500000),
    ('service-name', 'other-metric', -20),
    ('service-name', 'other-metric', 10),
]


TEST_KWARGS = [
    {'context': None, 'tags': None, 'other_extraneous_kwarg': 'ignored!'},
    {'context': {'remote-host': 'dns-host-3'}, 'tags': None},
    {'context': None, 'tags': ['v40']},
    {'context': {'type': 'active'}, 'tags': ['v40']},
    {'context': {'type': 'active'}, 'extraneous_kwarg': 'should be ignored'}
]


@pytest.mark.parametrize('key_name_val,kwargs', zip(
    TEST_KEY_NAME_VAL, TEST_KWARGS))
def test_ffwdrelay_create_metric(test_config, key_name_val, kwargs):
    """Creates metric for all arguments."""
    key, name, val = key_name_val
    test_config['key'] = key
    relay = ffwd.SimpleFfwdRelay(test_config)
    actual = relay._create_metric(name, val, **kwargs)

    attrs = kwargs['context'] or {}
    attrs.update({'what': name})
    expected = {
        'key': key,
        'attributes': attrs,
        'value': val,
        'type': 'metric'
    }
    assert expected == actual


@pytest.fixture
def ffwdrelay_and_metrics_sent(test_config, mock_udp_client_and_metrics_sent):
    mock_udp_client, metrics_sent = mock_udp_client_and_metrics_sent
    relay = ffwd.SimpleFfwdRelay(test_config)
    relay.udp_client = mock_udp_client
    return relay, metrics_sent


@pytest.mark.asyncio
@pytest.mark.parametrize('kwargs', TEST_KWARGS)
async def test_ffwdrelay_incr(ffwdrelay_and_metrics_sent, kwargs):
    """Creates and sends metrics with value 1."""
    ffwdrelay, metrics_sent = ffwdrelay_and_metrics_sent
    expected = [ffwdrelay._create_metric('some-increasing-value', 1, **kwargs)]
    await ffwdrelay.incr('some-increasing-value', **kwargs)
    assert expected == metrics_sent


@pytest.fixture
def ffwdrelay(ffwdrelay_and_metrics_sent):
    return ffwdrelay_and_metrics_sent[0]


@pytest.mark.parametrize('kwargs', TEST_KWARGS)
def test_ffwdrelay_timer(ffwdrelay, kwargs):
    """Returns initialized timer."""
    expected_metric = ffwdrelay._create_metric('some-timer', None, **kwargs)
    actual = ffwdrelay.timer('some-timer', **kwargs)
    assert isinstance(actual, ffwd.FfwdTimer)
    assert expected_metric == actual.metric
    assert ffwdrelay.time_unit == actual.time_unit
    assert ffwdrelay.udp_client == actual.udp_client


@pytest.mark.asyncio
@pytest.mark.parametrize('kwargs', TEST_KWARGS)
async def test_ffwdrelay_set(ffwdrelay_and_metrics_sent, kwargs):
    """Creates and sends metric with arbitrary value."""
    ffwdrelay, metrics_sent = ffwdrelay_and_metrics_sent
    expected = [
        ffwdrelay._create_metric('some-measure', 42, **kwargs)
    ]
    await ffwdrelay.set('some-measure', 42, **kwargs)
    assert expected == metrics_sent


@pytest.mark.asyncio
async def test_cleanup(ffwdrelay):
    """Raises no errors."""
    await ffwdrelay.cleanup()
