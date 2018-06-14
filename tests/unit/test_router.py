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

import pytest
import zope.interface

from gordon import interfaces
from gordon import router


@pytest.fixture()
def router_inst(loaded_config, inited_plugins, plugin_kwargs):
    inited_plugins.pop('runnable')
    route_config = loaded_config['core']['route']
    router_inst = router.GordonRouter(
            route_config, plugins=inited_plugins.values(), **plugin_kwargs)
    return router_inst


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


@pytest.fixture
def event_msg(mocker):
    msg = EventMsgStub(mocker)
    msg.phase = 'consume'
    return msg


@pytest.mark.parametrize('has_enricher', [True, False])
def test_init_router(has_enricher, inited_plugins, plugin_kwargs):
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
        exp_phase_route, plugins=inited_plugins.values(), **plugin_kwargs)

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
async def test_route_invalid_msg(router_inst, caplog, mocker, monkeypatch):
    event_msg = mocker.Mock()
    mock_next_phase = mocker.Mock()
    monkeypatch.setattr(router_inst, '_get_next_phase', mock_next_phase)

    await router_inst._route(event_msg)

    assert 1 == len(caplog.records)
    mock_next_phase.assert_not_called()


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

    assert 1 == mock_route_call_count
    assert [((event_msg,), {})] == mock_route_call_args


@pytest.fixture
def event_loop_mock(mocker, monkeypatch):
    mock = mocker.Mock()
    monkeypatch.setattr('gordon.router.asyncio.get_event_loop', mock)
    return mock.return_value


@pytest.mark.asyncio
async def test_run(caplog, event_loop_mock, router_inst, mocker, monkeypatch):
    poll_mock = mocker.Mock()
    monkeypatch.setattr(router_inst, '_poll_channel', poll_mock)

    await router_inst.run()

    event_loop_mock.create_task.assert_called_once_with(poll_mock.return_value)
    assert 1 == len(caplog.records)
