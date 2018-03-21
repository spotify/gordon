# -*- coding: utf-8 -*-
# Copyright (c) 2017 Spotify AB
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

from zope.interface import Attribute
from zope.interface import Interface


class IEventMessage(Interface):
    """A discrete unit of work for Gordon to process.

    Gordon expects plugins to return or accept objects that implement this
    interface in order to route them to other plugins, and handle retries
    or cleanup in case of errors.
    """

    def __init__(msg_id, data, history_log, phase=None):
        """Initialize an EventMessage.

        Args:
            msg_id (str): Unique message identifier.
            data (dict): Data required to update DNS records.
            history_log (list): Log of actions performed on message.
            phase (str): Current phase.
        """

    def append_to_history(entry):
        """Append entry to the IEventMessage's history_log.

        Args:
            entry (str): Information to append to log.
        """


class IGenericPlugin(Interface):
    """**Do not** implement this interface directly.

    Use :interface:`IEventConsumerClient`, :interface:`IEnricherClient`,
    or :interface:`IPublisherClient` instead.
    """
    phase = Attribute('Plugin phase')

    def __init__(config, success_channel, error_channel, **plugin_kwargs):
        """Initialize a plugin object.

        Args:
            config (dict): plugin-specific configuration
            success_channel (asyncio.Queue): a channel for successfully
                processed :interface:`IEventMessage`s.
            error_channel (asyncio.Queue): a channel for
                :interface:`IEventMessage`s that were not processed due
                to problems.
            plugin_kwargs (dict): Plugin-specific keyword arguments. See
                specific interface declarations.
        """

    async def update_phase(event_msg):
        """Update the phase of a message to current phase.

        Args:
            event_msg (IEventMessage): message with stale phase.
        """

    async def run():
        """Start plugin in the main event loop.

        All plugins require explicit running in order to start consuming
        and publishing to the respective channels.
        """


class IEventConsumerClient(IGenericPlugin):
    """Ingest push/pull events for Gordon to process.

    The client also  receives both successful and failed
    :interface:`IEventMessage` objects from Gordon in order
    to perform cleanup if needed.
    """

    async def cleanup(event_msg):
        """Clean up tasks related to a message.

        Args:
            event_msg (IEventMessage): message at the end of its
                lifecycle.
        """


class IEnricherClient(IGenericPlugin):
    """Process (enrich) or filter events received by Gordon.

    Note that if no extra processing is required, the implementer can
    immediately push the received event into the success_channel.
    """

    async def process(event_msg):
        """Process message.

        Args:
            event_msg (IEventMessage): message to process.
        """


class IPublisherClient(IGenericPlugin):
    """Publish enriched events to their destination."""

    async def publish_changes(event_msg):
        """Publish an enriched event to its destination.

        Args:
            event_msg (IEventMessage): message ready to be sent to
                destination.
        """
