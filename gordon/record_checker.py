# -*- coding: utf-8 -*-
#
# Copyright 2017 Spotify AB
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
import logging
import time

from async_dns import types
from async_dns.resolver import ProxyResolver


class RecordChecker(object):

    def __init__(self, dns_ip):
        """Setup RecordChecker object

        Args:
            dns_ip: DNS ip server to query
        """
        self._dns_ip = dns_ip
        self._resolver = ProxyResolver()
        self._resolver.set_proxies([self._dns_ip])

    def _extract_record_data(self, record):
        """Extract record data from a record dict

        Args:
            record (dict): DNS record as a dict
        """
        return record.values()

    async def check_record(self, record, timeout=60):
        """Measures the time for a DNS record to become available.

        Query a provided DNS server multiple time until
            the reply matches the information in the
            record or until timeout is reached.

        Args:
            record (dict): DNS record as a dict
            with record properties
            timeout (int): time threshold to query the DNS server
        """
        start_time = time.time()

        name, rr_data, r_type, ttl = self._extract_record_data(record)
        r_type_code = types.get_code(r_type)

        record_found_in_dns_srv = False
        retries = 0
        sleep_time = 2

        while not record_found_in_dns_srv and \
                timeout > sleep_time:

            retries += 1
            resolver_res = await self._resolver.query(name, r_type_code)
            possible_ans = resolver_res.an

            record_found_in_dns_srv = \
                await self._check_resolver_ans(possible_ans, name,
                                               rr_data, ttl, r_type_code)

            sleep_time = self._get_wait_time_exp(retries)
            await asyncio.sleep(sleep_time)

        if not record_found_in_dns_srv:
            logging.info(
                f'Sending metric record-checker-failed: {record}')
        else:
            final_time = float(time.time() - start_time)
            logging.info(final_time)

    async def _check_resolver_ans(
            self, dns_ans_lst, name, rr_data, ttl, r_type_code):
        """Check if resolver answer is equal to record data.

        Args:
            dns_ans_lst (list): DNS answer list contains record objects
            name (str): record name
            rr_data (list): list of ips for the record
            ttl (int): record time ot live info
            r_type_code (int): record type code

        Returns:
            boolean indicating if DNS ans data is equal to record data
        """
        type_filtered_lst = [
            ans for ans in dns_ans_lst if ans.qtype == r_type_code
        ]

        # check to see that type_filtered_lst has
        # the same number of records as record rr_data
        if len(type_filtered_lst) != len(rr_data):
            return False

        # check each record data is equal to the given data
        for rec in type_filtered_lst:
            conditions = [name == rec.name,
                          rec.data in rr_data,
                          rec.ttl == ttl]

            # if ans record data is not equal
            # to the given data return False
            if not all(conditions):
                return False

        return True

    def _get_wait_time_exp(self, retries):
        """Returns the next wait interval, using an exponential back off"""
        return pow(2, retries)
