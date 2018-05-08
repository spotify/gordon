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

import async_dns
from async_dns.resolver import ProxyResolver

from gordon import exceptions


class RecordChecker(object):

    def __init__(self, dns_ip):
        """Setup RecordChecker object.

        Args:
            dns_ip: DNS server IP to query.
        """
        self._dns_ip = dns_ip
        self._resolver = ProxyResolver()
        try:
            self._resolver.set_proxies([self._dns_ip])
        except async_dns.address.InvalidHost as e:
            msg = f'RecordChecker got invalid DNS server IP: {e}.'
            raise exceptions.InvalidDNSHost(msg)

    def _extract_record_data(self, record):
        """Extract record data from a record dict.

        Args:
            record (dict): DNS record as a dict.

        Returns:
            The record data: name, rrdata, type and ttl.
        """
        return record.values()

    async def check_record(self, record, timeout=60):
        """Measures the time for a DNS record to become available.

        Query a provided DNS server multiple times until the reply matches the
        information in the record or until timeout is reached.

        Args:
            record (dict): DNS record as a dict with record properties.
            timeout (int): Time threshold to query the DNS server.
        """
        start_time = time.time()

        name, rr_data, r_type, ttl = self._extract_record_data(record)
        r_type_code = async_dns.types.get_code(r_type)

        resolvable_record = False
        retries = 0
        sleep_time = 5

        while not resolvable_record and \
                timeout > retries * sleep_time:

            retries += 1
            resolver_res = await self._resolver.query(name, r_type_code)
            possible_ans = resolver_res.an

            resolvable_record = \
                await self._check_resolver_ans(possible_ans, name,
                                               rr_data, ttl, r_type_code)

            if not resolvable_record:
                await asyncio.sleep(sleep_time)

        if not resolvable_record:
            logging.info(
                f'Sending metric record-checker-failed: {record}.')
        else:
            final_time = float(time.time() - start_time)
            success_msg = (f'This record: {record} took {final_time} to '
                           'register.')
            logging.info(success_msg)

    async def _check_resolver_ans(
            self, dns_answer_list, record_name,
            record_data_list, record_ttl, record_type_code):
        """Check if resolver answer is equal to record data.

        Args:
            dns_answer_list (list): DNS answer list contains record objects.
            record_name (str): Record name.
            record_data_list (list): List of data values for the record.
            record_ttl (int): Record time-to-live info.
            record_type_code (int): Record type code.

        Returns:
            boolean indicating if DNS answer data is equal to record data.
        """
        type_filtered_list = [
            ans for ans in dns_answer_list if ans.qtype == record_type_code
        ]

        # check to see that type_filtered_lst has
        # the same number of records as record_data_list
        if len(type_filtered_list) != len(record_data_list):
            return False

        # check each record data is equal to the given data
        for rec in type_filtered_list:
            conditions = [rec.name == record_name,
                          rec.ttl == record_ttl,
                          rec.data in record_data_list]

            # if ans record data is not equal
            # to the given data return False
            if not all(conditions):
                return False

        return True
