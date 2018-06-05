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


# TODO/NOTE (lynn): This is a temporary helper function to alias
#                   entrypoints of plugins to a common name. In the
#                   future, plugin interfaces will be updated to have a
#                   common name for their entrypoint.
def _set_plugin_entrypoint_aliases(plugin_dict):
    # e.g. enricher_inst.process => enricher_inst.handle_message
    entrypoints = {
        'enricher': 'process',
        'publisher': 'publish_changes',
        'event_consumer': 'cleanup',
    }
    for plugin_name, func in entrypoints.items():
        try:
            plugin = plugin_dict[plugin_name]
        except KeyError:  # if no enricher
            continue
        entry_point = getattr(plugin, func)
        setattr(plugin, 'handle_message', entry_point)
    return plugin_dict


class GordonRouter:
    """Route messages to the appropriate plugin destination.

    .. attention::

        `error_channel` is currently not used in this router, and may
        be removed entirely from all interface definitions.

    Args:
        success_channel (asyncio.Queue): A sink for successfully
            processed :class:`gordon.interfaces.IEventMessage` s.
        error_channel (asyncio.Queue): A sink for
            :class:`gordon.interfaces.IEventMessage` s that were not
            processed due to problems.
        plugins (dict): Implemented plugin provider names mapped to
            their instantiated objects.
    """
    # TODO (lynn): Ideally this is configurable/extendable in future
    #              iterations of gordon.
    PHASE_TO_PLUGIN_MAPPER = {
        'enrich': 'enricher',
        'publish': 'publisher',
        'cleanup': 'event_consumer',
    }
    FINAL_PHASES = ('cleanup',)

    def __init__(self, success_channel, error_channel, plugins):
        self.success_channel = success_channel
        self.error_channel = error_channel
        self.plugins = _set_plugin_entrypoint_aliases(plugins)
        self.phase_route = self._setup_phase_route()

    # TODO (lynn): Ideally this is configurable/extendable in future
    #              iterations of gordon.
    def _setup_phase_route(self):
        route = {
            'consume': 'publish',
            'publish': 'cleanup',
            'cleanup': 'cleanup',
        }
        if 'enricher' in self.plugins:
            route['consume'] = 'enrich'
            route['enrich'] = 'publish'
        return route

    def _get_next_phase(self, event_msg):
        try:
            next_phase = self.phase_route[event_msg.phase]
            msg = f'Routing message {event_msg} to phase "{next_phase}".'
            logging.debug(msg)

        except KeyError:
            msg = (f'Message "{event_msg}" has an unknown phase: '
                   f'"{event_msg.phase}". Dropping message.')
            logging.error(msg)
            next_phase = 'cleanup'
        return next_phase

    async def _route(self, event_msg, next_phase=None):
        if not interfaces.IEventMessage.providedBy(event_msg):
            msg = (f'Ignoring message "{event_msg}". Does not correctly '
                   'implement `IEventMessage`.')
            logging.warn(msg)
            return

        if not next_phase:
            next_phase = self._get_next_phase(event_msg)

        event_msg.update_phase(next_phase)
        next_plugin_name = self.PHASE_TO_PLUGIN_MAPPER[next_phase]
        plugin = self.plugins[next_plugin_name]

        try:
            await plugin.handle_message(event_msg)
            # don't add a successfully dropped message back onto channel
            if next_phase not in self.FINAL_PHASES:
                msg = f'Adding message "{event_msg}" to success channel.'
                event_msg.append_to_history(msg, event_msg.phase)
                await self.success_channel.put(event_msg)

        except Exception as e:
            msg = f'Dropping message "{event_msg}" due to exception: "{e}"'
            event_msg.append_to_history(msg, event_msg.phase)
            logging.warn(msg, exc_info=e)
            await self._route(event_msg, 'cleanup')

    async def _poll_channel(self):
        while True:
            event_msg = await self.success_channel.get()

            # graceful shutdown
            if event_msg is None:
                msg = 'Received TERM signal, shutting down router...'
                logging.info(msg)
                # TODO (lynn): potentially propagate signal all plugins
                #              to clean up rather than just breaking
                break

            await self._route(event_msg)

    async def run(self):
        """Entrypoint to route messages between plugins."""
        logging.info('Starting message router...')
        loop = asyncio.get_event_loop()
        loop.create_task(self._poll_channel())
