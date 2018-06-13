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
"""

Gordon ships with a simple `ffwd <https://github.com/spotify/ffwd>`_
metrics implementation, which can be enabled via configuration. This
module contains the SimpleFfwdRelay, and all required classes that it
uses to send messsages to the ffwd daemon via UDP.

The `SimpleFfwdRelay` requires no configuration, but can be customized.
The defaults that may be overridden are shown below.

.. code-block:: ini

    [ffwd]
    # to identify the service creating metrics
    key = 'gordon-service'

    # the address of the ffwd daemon (see: UDPClient)
    ip = "127.0.0.9"
    port = 19000

    # a scaling factor for timing (see: FfwdTimer)
    time_unit = 1E9

"""

import asyncio
import json
import time

import zope.interface

from gordon import interfaces


class UDPClientProtocol(asyncio.DatagramProtocol):
    """Protocol for sending one-off messages via UDP.

    Args:
        message (bytes): Message for ffwd agent.
    """
    def __init__(self, message):
        self.message = message
        self.transport = None

    def connection_made(self, transport):
        """Create connection, use to send message and close.

        Args:
            transport (asyncio.DatagramTransport): Transport used for sending.
        """
        self.transport = transport
        self.transport.sendto(self.message)
        self.transport.close()


class UDPClient:
    """Client for sending UDP datagrams.

    Args:
        ip (str): (optional) Destination IP address (default: 127.0.0.1).
        port (int): (optional) Destination port (default: 9000).
        loop (asyncio.AbstractEventLoop impl): (optional) Event loop.
    """

    DEFAULT_IP = '127.0.0.1'
    DEFAULT_PORT = 19000

    def __init__(self, ip=None, port=None, loop=None):
        self.ip = ip or self.DEFAULT_IP
        self.port = port or self.DEFAULT_PORT
        self.loop = loop or asyncio.get_event_loop()

    async def send(self, metric):
        """Transform metric to JSON bytestring and send to server.

        Args:
            metric (dict): Complete metric to send as JSON.
        """
        message = json.dumps(metric).encode('utf-8')
        await self.loop.create_datagram_endpoint(
            lambda: UDPClientProtocol(message),
            remote_addr=(self.ip, self.port))


@zope.interface.implementer(interfaces.ITimer)
class FfwdTimer:
    """Timer which sends UDP messages to FFWD on completion.

    Args:
        metric (dict): Dict representation of the metric to send.
        udp_client (UDPClient): A metric sending client.
        time_unit (number): (optional) Scale time unit for use with
            time.perf_counter(), for example: 1E9 to send nanoseconds.
    """
    def __init__(self, metric, udp_client, time_unit=None):
        self.metric = metric
        self.udp_client = udp_client
        self.time_unit = time_unit or 1

    async def __aenter__(self):
        """Enter context manager to start timing."""
        await self.start()
        return self

    async def __aexit__(self, *args):
        """Exit context manager to stop timing."""
        await self.stop()

    async def start(self):
        """Start timer."""
        self._start_time = time.perf_counter()

    async def stop(self):
        """Stop timer."""
        time_elapsed = time.perf_counter() - self._start_time
        self.metric['value'] = time_elapsed * self.time_unit
        await self.udp_client.send(self.metric)


@zope.interface.implementer(interfaces.IMetricRelay)
class SimpleFfwdRelay:
    """Metrics relay which sends to FFWD immediately.

    The relay does no client-side aggregation and metrics are
    emitted immediately. The relay uses a combination of the `key and
    attributes fields <https://github.com/spotify/ffwd/tree/master/
    modules/json>`_ to semantically identify metrics in ffwd.

    Args:
        config (dict): Configuration with optional keys described above.
    """
    def __init__(self, config):
        self.key = config.get('key', 'gordon-service')
        self.udp_client = UDPClient(
            config.get('ffwd_ip'), config.get('ffwd_port'))
        self.time_unit = config.get('time_unit')

    def _create_metric(self, metric_name, value, context, **kwargs):
        attrs = context or {}
        attrs['what'] = metric_name

        metric = {
            'key': self.key,
            'attributes': attrs,
            'value': value,
            'type': 'metric'
        }
        return metric

    async def incr(self, metric_name, value=1, context=None, **kwargs):
        """Increase a metric by 1 or a given amount.

        Args:
            metric_name (str): Identifier of the metric.
            value (int): (optional) Value with which to increase the metric
                (default: 1).
            context (dict): (optional) Additional key-value pairs which further
                describe the metric, for example: {'remote-host': '1.2.3.4'}
        """
        await self.set(metric_name, value, context, **kwargs)

    def timer(self, metric_name, context=None, **kwargs):
        """Create a FfwdTimer.

        Args:
            metric_name (str): Identifier of the metric.
            context (dict): (optional) Additional key-value pairs which further
                describe the metric, for example: {'unit': 'seconds'}
        """
        metric = self._create_metric(metric_name, None, context, **kwargs)
        return FfwdTimer(metric, self.udp_client, self.time_unit)

    async def set(self, metric_name, value, context=None, **kwargs):
        """Set a metric to a given value.

        Args:
            metric_name (str): Identifier of the metric.
            value (number): The value of the metric.
            context (dict): (optional) Additional key-value pairs which further
                describe the metric, for example: {'app-version': '1.5.3'}
        """
        metric = self._create_metric(metric_name, value, context, **kwargs)
        await self.udp_client.send(metric)

    async def cleanup(self):
        """Not used."""
        pass
