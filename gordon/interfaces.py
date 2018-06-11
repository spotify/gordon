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

    def append_to_history(entry, plugin_phase):
        """Append entry to the IEventMessage's history_log.

        Args:
            entry (str): Information to append to log.
            plugin_phase (str): Phase of plugin that created the log
                entry message.
        """

    def update_phase(new_phase):
        """Update the phase of a message to new phase.

        Args:
            new_phase (str): Phase to update the message to.
        """


class IGenericPlugin(Interface):
    """**Do not** implement this interface directly.

    Use :py:class:`gordon.interfaces.IEventConsumerClient`,
    :py:class:`gordon.interfaces.IEnricherClient`,
    or :py:class:`gordon.interfaces.IPublisherClient` instead.
    """
    phase = Attribute('Plugin phase')

    def __init__(config, success_channel, error_channel, metrics):
        """Initialize an EventClient object.

        Args:
            config (dict): Plugin-specific configuration.
            success_channel (asyncio.Queue): A sink for successfully processed
                IEventMessages.
            error_channel (asyncio.Queue): A sink for IEventMessages that were
                not processed due to problems.
            metrics (obj): Optional obj used to emit metrics.
        """

    async def shutdown():
        """Gracefully shutdown plugin."""


class IEventConsumerClient(IGenericPlugin):
    """Client for ingesting push/pull events for Gordon to process.

    The client also receives both successful and failed
    :py:class:`gordon.interfaces.IEventMessage` objects from Gordon in order
    to perform cleanup if needed.
    """

    async def run():
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


class IMetricRelay(Interface):
    """Manage Gordon metrics."""

    async def incr(metric_name, value=1, context=None, **kwargs):
        """Increase a metric by 1 or a given amount.

        Args:
            metric_name (str): Identifier of the metric.
            value (int): (optional) Value with which to increase the metric.
            context (dict): (optional) Additional key-value pairs which further
                describe the metric, for example: {'remote-host': '1.2.3.4'}
        """

    def timer(metric_name, context=None, **kwargs):
        """Get a timer object which implements ITimer.

        Args:
            metric_name (str): Identifier of the metric.
            context (dict): (optional) Additional key-value pairs which further
                describe the metric, for example: {'unit': 'seconds'}
        """

    async def set(metric_name, value, context=None, **kwargs):
        """Set a metric to a given value.

        Args:
            metric_name (str): Identifier of the metric.
            value (number): The value of the metric.
            context (dict): (optional) Additional key-value pairs which further
                describe the metric, for example: {'app-version': '1.5.3'}
        """

    async def cleanup(**kwargs):
        """Perform cleanup tasks related to metrics handling."""


class ITimer(Interface):
    """Timer supporting both manual operation and use as a context manager."""

    async def __aenter__():
        """Enter context manager to start timing."""

    async def __aexit__(type, value, traceback):
        """Exit context manager to stop timing."""

    async def start():
        """Start timing."""

    async def stop():
        """End timing."""
