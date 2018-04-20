import asyncio
import logging
import time

from async_dns import types
from async_dns.resolver import ProxyResolver


class RecordChecker(object):
    QUERYING_THRESHOLD = 60

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

    async def check_record(self, record):
        """Asynchronously queries a DNS server for a given record
            to check how long it takes the record to become available.

        Args:
            record (dict): DNS record as a dict
            with record properties

        """
        start_time = time.time()

        name, rr_data, r_type, ttl = self._extract_record_data(record)
        r_type_code = types.get_code(r_type)

        record_found_in_dns_srv = False
        query_tries = 0

        while not record_found_in_dns_srv and\
                self.QUERYING_THRESHOLD != query_tries:

            query_tries += 1
            resolver_res = await self._resolver.query(name, r_type_code)
            possible_ans = resolver_res.an

            record_found_in_dns_srv = \
                await self._check_resolver_ans(possible_ans, name,
                                               rr_data, ttl, r_type_code)
            await asyncio.sleep(1)

        if not record_found_in_dns_srv:
            logging.info(
                f'Sending metric record-checker-failed: {record}')
        else:
            final_time = float(time.time() - start_time)
            logging.info(final_time)

    async def _check_resolver_ans(
            self, dns_ans_lst, name, rr_data, ttl, r_type_code):
        """Check if resolver ans is equal to record data.

        Args:
            dns_ans_lst (list): DNS answer list contains record objects
            name (str): record name
            rr_data (list): list of ips for the record
            ttl (int): record time ot live info
            r_type_code (int): record type code

        Returns:
            boolean indicating if DNS ans data is equal to record data
        """
        type_filtered_lst = \
            list(filter(lambda r: r.qtype == r_type_code, dns_ans_lst))

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


if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    record_check = RecordChecker('8.8.8.8')
    my_rec = {
        "name": "ns1.dnsowl.com",
        "rrdatas": ["198.251.84.16", "173.254.242.221", "185.34.216.159"],
        "type": "A",
        "ttl": 4945
    }
    loop.run_until_complete(record_check.check_record(my_rec))
