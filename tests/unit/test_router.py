# -*- coding: utf-8 -*-
#
# Copyright 2018 Spotify AB
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

import asyncio

import pytest
import zope.interface

from gordon import interfaces
from gordon import router


@zope.interface.implementer(interfaces.IEventMessage)
class EventMsgStub:
    def __init__(self, mocker):
        self.msg_id = 1234
        self.phase = None
        self._mock_update_phase_count = 0
        self._mock_append_to_history = 0

    def update_phase(self, new_phase):
        self.phase = new_phase
        self._mock_update_phase_count += 1

    def append_to_history(self, *args, **kwargs):
        self._mock_append_to_history += 1

    def __repr__(self):
        return f'EventMsgStub(msg_id={self.msg_id})'


@zope.interface.implementer(interfaces.IMetricRelay)
class MetricRelayStub:
    def __init__(self, config):
        self.config = config
        self._mock_incr_call_count = 0
        self._mock_incr_call_args = []

        self._mock_timer_call_count = 0
        self._mock_timer_call_args = []

        self._mock_set_call_count = 0
        self._mock_set_call_args = []

    async def incr(self, metric_name, value=1, context=None, **kwargs):
        self._mock_incr_call_count += 1
        self._mock_incr_call_args.append((metric_name, value, context, kwargs))

    def timer(self, metric_name, context=None, **kwargs):
        self._mock_timer_call_count += 1
        self._mock_timer_call_args.append((metric_name, context, kwargs))
        return TimerStub(metric_name)

    async def set(self, metric_name, value, context=None, **kwargs):
        self._mock_set_call_count += 1
        self._mock_set_call_args.append((metric_name, value, context, kwargs))


@zope.interface.implementer(interfaces.ITimer)
class TimerStub:
    def __init__(self, metric_name):
        self.metric_name = metric_name
        self._mock_start_call_count = 0
        self._mock_stop_call_count = 0

    async def start(self, *args, **kwargs):
        self._mock_start_call_count += 1

    async def stop(self, *args, **kwargs):
        self._mock_stop_call_count += 1


@pytest.fixture
def metrics():
    return MetricRelayStub({})


@pytest.fixture()
def router_inst(loaded_config, inited_plugins, metrics, plugin_kwargs):
    inited_plugins.pop('runnable')
    route_config = loaded_config['core']['route']
    router_inst = router.GordonRouter(
            route_config, plugins=inited_plugins.values(), metrics=metrics,
            **plugin_kwargs)
    return router_inst


@pytest.fixture
def event_msg(mocker):
    msg = EventMsgStub(mocker)
    msg.phase = 'consume'
    return msg


@pytest.mark.parametrize('has_enricher', [True, False])
def test_init_router(has_enricher, inited_plugins, plugin_kwargs, metrics):
    exp_phase_route = {
        'consume': 'publish',
        'publish': 'cleanup',
        'cleanup': 'cleanup'
    }

    exp_phase_map = {
        'consume': interfaces.IRunnable,
        'publish': interfaces.IMessageHandler,
        'cleanup': interfaces.IMessageHandler
    }

    inited_plugins.pop('runnable')
    if has_enricher:
        exp_phase_route['consume'] = 'enrich'
        exp_phase_route['enrich'] = 'publish'
        exp_phase_map['enrich'] = interfaces.IMessageHandler
    else:
        inited_plugins.pop('enricher')

    router_inst = router.GordonRouter(
        exp_phase_route, plugins=inited_plugins.values(), metrics=metrics,
        **plugin_kwargs)

    assert exp_phase_route == router_inst.phase_route
    for phase, plugin in router_inst.phase_plugin_map.items():
        assert exp_phase_map[phase].providedBy(plugin)


@pytest.mark.parametrize('current_phase,exp_next_phase', (
    ('consume', 'enrich'),
    ('its_not_a_phase_mom', 'cleanup'),
))
def test_get_next_phase(current_phase, exp_next_phase, router_inst, event_msg,
                        caplog):
    event_msg.phase = current_phase
    next_phase = router_inst._get_next_phase(event_msg)

    assert exp_next_phase == next_phase
    assert 1 == len(caplog.records)


@pytest.mark.asyncio
@pytest.mark.parametrize('msg_exists,exp_start_count', (
    (True, 0),
    (False, 1),
))
async def test_add_message_in_flight(msg_exists, exp_start_count, router_inst,
                                     event_msg):
    if msg_exists:
        timer = router_inst.metrics.timer(
            'router-message-flight-duration', {'unit': 'seconds'})
        router_inst._messages_in_flight[event_msg.msg_id] = timer

    await router_inst._add_message_in_flight(event_msg)

    assert event_msg.msg_id in router_inst._messages_in_flight

    if not msg_exists:
        timer = router_inst._messages_in_flight[event_msg.msg_id]

    assert exp_start_count == timer._mock_start_call_count

    assert 'router-message-flight-duration' == timer.metric_name
    assert 1 == router_inst.metrics._mock_set_call_count

    exp_args = [('router-messages-in-flight', 1, None, {})]
    assert exp_args == router_inst.metrics._mock_set_call_args


@pytest.mark.asyncio
@pytest.mark.parametrize('phase,exp_stop_count,exp_msg_count', (
    ('cleanup', 1, 0),
    ('consume', 0, 1),
))
async def test_remove_message_in_flight(phase, exp_stop_count, exp_msg_count,
                                        router_inst, event_msg):
    event_msg.phase = phase
    timer = router_inst.metrics.timer(
        'router-message-flight-duration', {'unit': 'seconds'})
    router_inst._messages_in_flight[event_msg.msg_id] = timer

    await router_inst._remove_message_in_flight(event_msg)

    assert exp_msg_count == len(router_inst._messages_in_flight)
    assert exp_stop_count == timer._mock_stop_call_count
    assert 'router-message-flight-duration' == timer.metric_name
    assert 1 == router_inst.metrics._mock_set_call_count

    exp_args = [('router-messages-in-flight', exp_msg_count, None, {})]
    assert exp_args == router_inst.metrics._mock_set_call_args


@pytest.mark.asyncio
@pytest.mark.parametrize('raises,exp_call_count,exp_log_count', (
    (False, 0, 1),
    (True, 1, 2),
))
async def test_route(raises, exp_call_count, exp_log_count, event_msg,
                     router_inst, caplog, monkeypatch):

    mock_process_call_count = 0
    mock_process_call_args = []

    async def mock_process(*args, **kwargs):
        nonlocal mock_process_call_count
        nonlocal mock_process_call_args

        mock_process_call_count += 1
        mock_process_call_args.append((args, kwargs))
        if raises:
            raise Exception('foo')

    monkeypatch.setattr(
        router_inst.phase_plugin_map['enrich'], 'handle_message', mock_process)

    await router_inst._route(event_msg)

    assert 1 == mock_process_call_count
    assert [((event_msg,), {})] == mock_process_call_args
    assert 1 == event_msg._mock_append_to_history
    assert exp_log_count == len(caplog.records)
    actual_count = \
        router_inst.phase_plugin_map['cleanup']._mock_handle_message_count
    assert exp_call_count == actual_count


@pytest.mark.asyncio
async def test_route_no_phase_no_cleanup(event_msg, router_inst, caplog):
    del(router_inst.phase_plugin_map['cleanup'])
    event_msg.phase = 'blahblah'  # doesnt exist

    await router_inst._route(event_msg)
    assert 2 == len(caplog.records)  # unknown phase, drop


@pytest.mark.asyncio
@pytest.mark.parametrize('phase,raises,incr_count,incr_args', (
    ('consume', False, 1, [('router-update-message-phase', 1,
                            {'current': 'consume', 'next': 'enrich'},
                            {}), ]),
    ('publish', False, 2, [('router-update-message-phase', 1,
                            {'current': 'publish', 'next': 'cleanup'}, {}),
                           ('router-message-completed', 1, None, {})]),
    ('consume', True, 3, [('router-update-message-phase', 1,
                           {'current': 'consume', 'next': 'enrich'}, {}),
                          ('router-message-dropped', 1,
                           {'error': 'Exception'}, {}),
                          ('router-update-message-phase', 1,
                           {'current': 'enrich', 'next': 'cleanup'}, {})]),
))
async def test_route_metrics(phase, raises, incr_count, incr_args, router_inst,
                             event_msg, monkeypatch):
    """Various metrics are called when message is routed."""
    event_msg.phase = phase

    async def mock_handle_message(*args, **kwargs):
        if raises:
            raise Exception('foo')

    monkeypatch.setattr(
        router_inst.phase_plugin_map['enrich'], 'handle_message',
        mock_handle_message)

    await router_inst._route(event_msg)

    assert incr_count == router_inst.metrics._mock_incr_call_count
    assert incr_args == router_inst.metrics._mock_incr_call_args


@pytest.mark.asyncio
@pytest.mark.parametrize('enricher,raises', (
    (True, False),
    (True, True),
    (False, True),
    (False, False),
))
async def test_poll_channel(enricher, raises, router_inst, event_msg, caplog,
                            monkeypatch):
    if not enricher:
        router_inst.phase_route.pop('enrich')
        router_inst.phase_route['consume'] = 'publish'

    if raises:
        event_msg.phase = 'its_not_a_phase_mom'

    mock_route_call_count = 0
    mock_route_call_args = []

    async def mock_route(*args, **kwargs):
        nonlocal mock_route_call_count
        nonlocal mock_route_call_args

        mock_route_call_count += 1
        mock_route_call_args.append((args, kwargs))

    monkeypatch.setattr(router_inst, '_route', mock_route)

    await router_inst.success_channel.put(event_msg)
    await router_inst.success_channel.put(None)
    await router_inst._poll_channel()
    await router_inst._poll_channel()

    assert 1 == mock_route_call_count
    assert [((event_msg,), {})] == mock_route_call_args


@pytest.mark.asyncio
async def test_poll_channel_empty(router_inst, mocker, monkeypatch):
    mock_channel_get_call_count = 0

    async def mock_channel_get(*args, **kwargs):
        nonlocal mock_channel_get_call_count
        mock_channel_get_call_count += 1

    monkeypatch.setattr(router_inst.success_channel, 'get', mock_channel_get)

    assert router_inst.success_channel.empty()  # sanity check

    await router_inst._poll_channel()

    assert not mock_channel_get_call_count


@pytest.mark.asyncio
async def test_poll_channel_metrics(router_inst, event_msg, monkeypatch):
    """Various metrics are called when message is polled."""

    async def mock_route(*args, **kwargs):
        pass

    monkeypatch.setattr(router_inst, '_route', mock_route)

    mock_add_call_count = 0
    mock_add_call_args = []

    async def mock_add_message_in_flight(*args, **kwargs):
        nonlocal mock_add_call_count
        nonlocal mock_add_call_args

        mock_add_call_count += 1
        mock_add_call_args.append((args, kwargs))

    monkeypatch.setattr(
        router_inst, '_add_message_in_flight',
        mock_add_message_in_flight)

    mock_remove_call_count = 0
    mock_remove_call_args = []

    async def mock_remove_message_in_flight(*args, **kwargs):
        nonlocal mock_remove_call_count
        nonlocal mock_remove_call_args

        mock_remove_call_count += 1
        mock_remove_call_args.append((args, kwargs))

    monkeypatch.setattr(
        router_inst, '_remove_message_in_flight',
        mock_remove_message_in_flight)

    await router_inst.success_channel.put(event_msg)
    await router_inst.success_channel.put(None)

    await router_inst._poll_channel()

    assert 1 == mock_add_call_count
    assert 1 == mock_remove_call_count

    args = [((event_msg,), {}), ]
    assert args == mock_add_call_args
    assert args == mock_remove_call_args

    assert 1 == router_inst.metrics._mock_incr_call_count
    exp_args = [('router-message-consumed', 1, None, {})]
    assert exp_args == router_inst.metrics._mock_incr_call_args


@pytest.mark.asyncio
async def test_poll_channel_invalid_msg(router_inst, caplog, mocker,
                                        monkeypatch):
    event_msg = mocker.Mock()
    mock_next_phase = mocker.Mock()
    monkeypatch.setattr(router_inst, '_get_next_phase', mock_next_phase)
    await router_inst.success_channel.put(event_msg)

    await router_inst._poll_channel()

    assert 1 == len(caplog.records)
    mock_next_phase.assert_not_called()
    assert 1 == router_inst.metrics._mock_incr_call_count

    exp = (
        'router-message-dropped', 1, {'error': 'invalid-message-provider'}, {}
    )
    assert [exp, ] == router_inst.metrics._mock_incr_call_args


@pytest.fixture
def event_loop_mock(mocker, monkeypatch):
    mock = mocker.Mock()
    monkeypatch.setattr('gordon.router.asyncio.get_event_loop', mock)
    return mock.return_value


@pytest.mark.asyncio
async def test_run(caplog, event_loop_mock, router_inst, mocker, monkeypatch):

    mock_poll_channel_call_count = 0

    async def mock_poll_channel(*args, **kwargs):
        nonlocal mock_poll_channel_call_count
        mock_poll_channel_call_count += 1

    mock_wait_call_count = 0

    async def mock_wait(coroutines, timeout=None):
        nonlocal mock_wait_call_count

        if mock_wait_call_count > 0:
            for coro in coroutines:
                coro.close()
            raise asyncio.CancelledError()

        mock_wait_call_count += 1
        for coro in coroutines:
            await coro
        return (coroutines, set())

    monkeypatch.setattr(router_inst, '_poll_channel', mock_poll_channel)
    monkeypatch.setattr(asyncio, 'wait', mock_wait)

    try:
        await router_inst.run()
    except asyncio.CancelledError:
        pass

    assert 1 == len(caplog.records)
    assert 1 == mock_wait_call_count
    assert 1 == mock_poll_channel_call_count
