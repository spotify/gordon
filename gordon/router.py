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
"""
Core message routing logic for the plugins within Gordon Service.

Messages received on the success channel will be routed to the next
designated plugin phase. For example, a message that has a ``consume``
phase will be routed to the installed enricher provider (or publisher
provider if no enricher provider is installed).

If a message fails its next phase, its phase will be updated to ``drop``
and routed to the event consumer provider for cleanup.

.. attention::

    The :class:`GordonRouter` only supports the following two phase
    routes:

    1. consume -> enrich -> publish -> done
    2. consume -> publish -> done

    Future releases may support more configurable phase routings.

"""

import asyncio
import logging

from gordon import interfaces


class GordonRouter:
    """Route messages to the appropriate plugin destination.

    .. attention::

        `error_channel` is currently not used in this router, and may
        be removed entirely from all interface definitions.

    Args:
        phase_route (dict(str, str)): The route messages should follow.
        success_channel (asyncio.Queue): A sink for successfully
            processed :class:`gordon.interfaces.IEventMessage` s.
        error_channel (asyncio.Queue): A sink for
            :class:`gordon.interfaces.IEventMessage` s that were not
            processed due to problems.
        plugins (list): Instantiated message handling plugins.
        metrics (obj): Implemented :class:`IMetricRelay` interface
            to emit metrics.
    """
    # TODO (lynn): Ideally this is configurable/extendable in future
    #              iterations of gordon.
    FINAL_PHASES = ('cleanup',)

    def __init__(self, phase_route, success_channel, error_channel, plugins,
                 metrics):
        self.success_channel = success_channel
        self.error_channel = error_channel
        self.phase_plugin_map = self._get_phase_plugin_map(plugins)
        self.phase_route = phase_route
        self.metrics = metrics
        self._messages_in_flight = {}

    def _get_phase_plugin_map(self, plugins):
        phase_map = {p.phase: p for p in plugins}
        if not set(self.FINAL_PHASES) & set(phase_map):
            msg = ('No plugin implements a final phase, defaulting to '
                   'drop messages that are routed to these phases: '
                   f'{",".join(self.FINAL_PHASES)}.')
            logging.warn(msg)
        return phase_map

    def _get_next_phase(self, event_msg):
        try:
            next_phase = self.phase_route[event_msg.phase]
            msg = f'Routing message {event_msg.msg_id} to "{next_phase}".'
            logging.debug(msg)

        except KeyError:
            msg = (f'Message "{event_msg.msg_id}" has an unknown phase: '
                   f'"{event_msg.phase}", routing to "cleanup".')
            logging.error(msg)
            next_phase = 'cleanup'
        return next_phase

    async def _update_messages_in_flight(self):
        in_flight_count = len(self._messages_in_flight)
        await self.metrics.set(
            'router-messages-in-flight', value=in_flight_count)

    async def _add_message_in_flight(self, event_msg):
        if event_msg.msg_id not in self._messages_in_flight:
            context = {'unit': 'seconds'}
            timer = self.metrics.timer(
                'router-message-flight-duration', context=context)
            await timer.start()
            self._messages_in_flight[event_msg.msg_id] = timer

        await self._update_messages_in_flight()

    async def _remove_message_in_flight(self, event_msg):
        if event_msg.phase in self.FINAL_PHASES:
            timer = self._messages_in_flight.pop(event_msg.msg_id)
            await timer.stop()

        await self._update_messages_in_flight()

    async def _route(self, event_msg, force_cleanup=False):
        if force_cleanup:
            next_phase = 'cleanup'
        else:
            next_phase = self._get_next_phase(event_msg)

        context = {
            'current': event_msg.phase,
            'next': next_phase,
        }
        await self.metrics.incr('router-update-message-phase', context=context)

        event_msg.update_phase(next_phase)
        next_plugin = self.phase_plugin_map.get(next_phase)
        if next_phase in self.FINAL_PHASES and not next_plugin:
            msg = (f'Dropping message "{event_msg.msg_id}", final phase '
                   f'"{next_phase}" not implemented.')
            logging.debug(msg)
            return

        try:
            await next_plugin.handle_message(event_msg)
            # don't add a successfully dropped message back onto channel
            if next_phase not in self.FINAL_PHASES:
                msg = f'Adding message "{event_msg}" to success channel.'
                event_msg.append_to_history(msg, event_msg.phase)
                await self.success_channel.put(event_msg)
            elif next_phase in self.FINAL_PHASES and not force_cleanup:
                # if we're here, can assume message successfully went thru
                # the entire phase route and not dropped
                await self.metrics.incr('router-message-completed')

        except Exception as e:
            msg = (f'Routing message "{event_msg}" to cleanup due to exception:'
                   f' "{e}"')
            event_msg.append_to_history(msg, event_msg.phase)
            logging.warn(msg, exc_info=e)
            context = {'error': e.__class__.__name__}
            await self.metrics.incr('router-message-dropped', context=context)
            await self._route(event_msg, force_cleanup=True)

    async def _verify_message_impl(self, event_msg):
        if not interfaces.IEventMessage.providedBy(event_msg):
            msg = (f'Ignoring message "{event_msg.msg_id}". Does not correctly'
                   ' implement `IEventMessage`.')
            logging.warn(msg)

            context = {'error': 'invalid-message-provider'}
            await self.metrics.incr('router-message-dropped', context=context)
            return False
        return True

    async def _poll_channel(self):
        if not self.success_channel.empty():
            event_msg = await self.success_channel.get()

            # graceful shutdown
            if event_msg is None:
                msg = 'Received TERM signal, shutting down router...'
                logging.info(msg)
                # TODO (lynn): potentially propagate signal all plugins
                #              to clean up rather than just breaking
                return

            if not await self._verify_message_impl(event_msg):
                return

            await self.metrics.incr('router-message-consumed')
            await self._add_message_in_flight(event_msg)
            await self._route(event_msg)
            await self._remove_message_in_flight(event_msg)

    async def run(self):
        """Entrypoint to route messages between plugins."""
        logging.info('Starting message router...')

        coroutines = set()
        while True:
            coro = self._poll_channel()
            coroutines.add(coro)
            _, coroutines = await asyncio.wait(coroutines, timeout=0.1)
