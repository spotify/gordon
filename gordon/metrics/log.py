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
Gordon ships with a default IMetricRelay implementation, which
outputs metrics to the application logger using the standard
library `logging` module.

This implementation is used by default if no other IMetricRelay
implementation is loaded and chosen.

The default configuration that can be overriden is shown below.

.. code-block:: ini

    [metrics-logger]
    # One of the log levels available from the stdlib logging module.
    log_level = 'info'
    # A scaling factor for timing (see: LogTimer)
    time_unit = 1
"""

import collections
import logging
import time

import zope.interface

from gordon import interfaces


@zope.interface.implementer(interfaces.ITimer)
class LogTimer:
    """Timer that outputs metrics to the logger.

    Args:
        metric (dict): Metric to output.
        logger (.LoggerAdapter): Object used for outputting metrics.
        time_unit (number): (optional) Scale time unit for use with
            time.perf_counter(), for example: 1E9 to send nanoseconds.
    """
    def __init__(self, metric, logger, time_unit=1):
        self.metric = metric
        self.logger = logger
        self.time_unit = time_unit

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()

    async def start(self):
        """Start the timer."""
        self._start_time = time.perf_counter()

    async def stop(self):
        """Stop the timer and output the time delta to the logger."""
        time_elapsed = (
            time.perf_counter() - self._start_time) * self.time_unit
        self.metric['value'] = time_elapsed
        self.logger.log(self.metric)


class LoggerAdapter:
    """Configurable adapter that formats and outputs metrics.

    Args:
        level (str): Log level at which to output metric.
    """
    LOGFMT = '[{metric_name}] value: {value}'

    def __init__(self, level):
        self.level = getattr(logging, level.upper())
        self._logger = logging.getLogger('gordon.metrics-logger')

    def log(self, metric):
        """Format and output metric.

        Args:
            metric (dict): Complete metric.
        """
        message = self.LOGFMT.format(**metric)
        if metric['context']:
            message += ' context: {context}'.format(context=metric['context'])
        self._logger.log(self.level, message)


@zope.interface.implementer(interfaces.IMetricRelay)
class LogRelay:
    """Manage metrics that get output to a logger.

    Args:
        config (dict): Required keys:
            level (str): Log level of metrics log messages.
            time_unit (number): (optional) Scale time unit for use with
                LogTimer, for example: 1E9 to send nanoseconds.
    """
    def __init__(self, config):
        level = config.get('log_level', 'info')
        self.time_unit = config.get('time_unit', 1)
        self.logger = LoggerAdapter(level)
        self.counters = collections.defaultdict(int)

    def _create_metric(self, metric_name, value, context, **kwargs):
        context = context or {}

        return {
            'metric_name': metric_name,
            'value': value,
            'context': context
        }

    async def incr(self, metric_name, value=1, context=None, **kwargs):
        """Increase a metric counter by ``value`` and output result.

        Args:
            metric_name (str): Identifier of the metric.
            value (number): (optional) Value with which to increase the metric.
            context (dict): (optional) Additional key-value pairs which further
                describe the metric, for example: {'remote-host': '1.2.3.4'}
        """
        self.counters[metric_name] += value
        await self.set(metric_name, self.counters[metric_name], context,
                       **kwargs)

    def timer(self, metric_name, context=None, **kwargs):
        """Create a LogTimer.

        Args:
            metric_name (str): Identifier of the metric.
            context (dict): (optional) Additional key-value pairs which further
                describe the metric, for example: {'unit': 'milliseconds'}
        """
        metric = self._create_metric(metric_name, None, context, **kwargs)
        return LogTimer(metric, self.logger, self.time_unit)

    async def set(self, metric_name, value, context=None, **kwargs):
        """Output ``metric_name`` with ``value``.

        Args:
            metric_name (str): Identifier of the metric.
            value (number): (optional) Value of the metric.
            context (dict): (optional) Additional key-value pairs which further
                describe the metric, for example: {'app-version': '1.5.4'}
        """
        metric = self._create_metric(metric_name, value, context, **kwargs)
        self.logger.log(metric)

    async def cleanup(self):
        """Not used."""
        pass
