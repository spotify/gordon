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

import asyncio
import json
import time

import zope.interface

from gordon import interfaces


class FfwdClientProtocol(asyncio.DatagramProtocol):
    """Protocol for sending one-off messages to ffwd.

    Args:
        message (bytes): Message for ffwd agent.
    """
    def __init__(self, message):
        self.message = message
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        self.transport.sendto(self.message)
        self.transport.close()


class UDPClient:
    """Client for sending UDP datagrams.

    Args:
        ip (str): Destination IP address.
        port (int): Destination port.
        loop (asyncio.event_loop): (optional) Event loop.
    """
    def __init__(self, ip, port, loop=None):
        self.ip = ip
        self.port = port
        self.loop = loop or asyncio.get_event_loop()

    async def send(self, metric):
        """Transform metric to JSON bytestring and send to server.

        Args:
            metric (dict): Complete metric to send as JSON.
        """
        message = json.dumps(metric).encode('utf-8')
        await self.loop.create_datagram_endpoint(
            lambda: FfwdClientProtocol(message),
            remote_addr=(self.ip, self.port))


@zope.interface.implementer(interfaces.ITimer)
class FfwdTimer:
    """ITimer implementation which sends UDP messages to FFWD on completion.

    Args:
        metric (dict): Dict representation of the metric to send.
        udp_client (UDPClient): A metric sending client.
        time_unit (number): (optional) Scale time unit for use with time.time()
            (example: 1E9 to send nanoseconds).
    """
    def __init__(self, metric, udp_client, time_unit=1):
        self.metric = metric
        self.udp_client = udp_client
        self.time_unit = time_unit

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()

    async def start(self):
        self._start_time = time.time()

    async def stop(self):
        time_elapsed = (time.time() - self._start_time) * self.time_unit
        self.metric['value'] = time_elapsed
        await self.udp_client.send(self.metric)


@zope.interface.implementer(interfaces.IMetricRelay)
class FfwdRelay:
    """IMetricRelay implementation which sends metrics to FFWD immediately.

    Args:
        config (dict): Required keys:
            key (str): A key to identify the service as a whole.
            ffwd_ip (str): ffwd IP address.
            ffwd_port (int): ffwd port number.
            time_unit (number): Scale unit to use with timers.
    """
    def __init__(self, config):
        self.key = config['key']
        self.udp_client = UDPClient(config['ffwd_ip'], config['ffwd_port'])
        self.time_unit = config['time_unit']

    def _create_metric(self, metric_name, value, **kwargs):
        attrs = kwargs.get('attrs') or {}
        tags = kwargs.get('tags') or []

        attrs['what'] = metric_name
        return {
            'key': self.key,
            'attributes': attrs,
            'value': value,
            'type': 'metric',
            'tags': tags
        }

    async def incr(self, metric_name, value=1, **kwargs):
        await self.set(metric_name, value, **kwargs)

    def timer(self, metric_name, **kwargs):
        metric = self._create_metric(metric_name, None, **kwargs)
        return FfwdTimer(metric, self.udp_client, self.time_unit)

    async def set(self, metric_name, value, **kwargs):
        metric = self._create_metric(metric_name, value, **kwargs)
        await self.udp_client.send(metric)

    async def cleanup(self):
        pass
