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

    Use :py:class:`gordon.interfaces.IEventConsumerClient`,
    :py:class:`gordon.interfaces.IEnricherClient`,
    or :py:class:`gordon.interfaces.IPublisherClient` instead.
    """
    phase = Attribute('Plugin phase')

    def __init__(config, success_channel, error_channel, loop, metrics=None):
        """Initialize an EventClient object.

        Args:
            config (dict): Plugin-specific configuration.
            success_channel (asyncio.Queue): A sink for successfully processed
                IEventMessages.
            error_channel (asyncio.Queue): A sink for IEventMessages that were
                not processed due to problems.
            loop (obj): Object implementing asyncio.AbstractEventLoop.
            metrics (obj): Optional obj used to emit metrics.
        """

    async def update_phase(event_msg):
        """Update the phase of a message to current phase.

        Args:
            event_msg (IEventMessage): Message with stale phase.
        """


class IEventConsumerClient(IGenericPlugin):
    """Client for ingesting push/pull events for Gordon to process.

    The client also receives both successful and failed
    :py:class:`gordon.interfaces.IEventMessage` objects from Gordon in order
    to perform cleanup if needed.
    """

    async def start():
        """Begin consuming messages using the provided event loop."""

    async def cleanup(event_msg):
        """Perform cleanup tasks related to a message.

        Args:
            event_msg (IEventMessage): Message at the end of its life cycle.
        """


class IEnricherClient(IGenericPlugin):
    """Client for processing (enriching) or filtering events received by Gordon.

    Note that if no extra processing is required, the implementer can
    immediately push the received event into the success_channel.
    """

    async def process(event_msg):
        """Process message.

        Args:
            event_msg (IEventMessage): Message to process.
        """


class IPublisherClient(IGenericPlugin):
    """Client for publishing processed events to their destination."""

    async def publish_changes(event_msg):
        """Publish processed event to its destination.

        Args:
            event_msg (IEventMessage): Message ready to be sent to destination.
        """
