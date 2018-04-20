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

import pytest
from async_dns import Record

from gordon import record_checker


#####
# Tests & fixtures for running record checker
#####

@pytest.fixture
def record_checker_instance():
    dnc_ip = '8.8.8.8'
    return record_checker.RecordChecker(dnc_ip)


@pytest.fixture
def record_1(mocker):
    record_mock = mocker.Mock(Record)
    record_mock.qtype = 1
    record_mock.name = 'ns1.dnsowl.com'
    record_mock.data = '185.34.216.159'
    record_mock.ttl = 10686
    return record_mock


@pytest.fixture
def record_2(record_1):
    record_1.data = '173.254.242.221'
    return record_1


@pytest.fixture
def record_3(record_1):
    record_1.data = '198.251.84.16'
    return record_1


@pytest.fixture
def dns_query_response(mocker, record_1, record_2, record_3):
    dns_res_mock = mocker.Mock()
    dns_res_mock.an = [record_1, record_2, record_3]
    return dns_res_mock


@pytest.fixture
def get_mock_coro(mocker):
    """Create a mock-coro pair.
    The coro can be used to patch an async method while the mock can
    be used to assert calls to the mocked out method.
    """
    def _create_mock_coro_pair():
        mock = mocker.Mock()

        async def _coro(*args, **kwargs):
            return mock(*args, **kwargs)
        return mock, _coro
    return _create_mock_coro_pair


@pytest.fixture
def mock_resolve_query(mocker, get_mock_coro, record_checker_instance):
    mock, _coroutine = get_mock_coro()
    mocker.patch.object(record_checker_instance._resolver, "query", _coroutine)
    return mock


@pytest.mark.asyncio
async def test_check_record_time_range_check(
        record_checker_instance, caplog,
        mock_resolve_query, dns_query_response):
    """Test the time it took to check a record is in expected range"""
    record_to_check = {
        "name": "ns1.dnsowl.com",
        "rrdatas": ["198.251.84.16", "173.254.242.221", "185.34.216.159"],
        "type": "A",
        "ttl": 10686
    }

    mock_resolve_query.return_value = dns_query_response

    await record_checker_instance.check_record(record_to_check)
    time_it_took_to_check_record = float(caplog.records[0].msg)
    assert 0 < time_it_took_to_check_record < 1.005


@pytest.mark.asyncio
async def test_check_record_failed(
        mocker, get_mock_coro,
        record_checker_instance, caplog,
        mock_resolve_query, dns_query_response):
    """Test we get a failure logging msg for the case of failure:
        we didn't get available record from the DNS"""
    record_to_check = {
        "name": "ns1.dnsowl.com",
        "rrdatas": ["198.251.84.15", "173.254.242.221", "185.34.216.159"],
        "type": "A",
        "ttl": 10686
    }

    mock_resolve_query.return_value = dns_query_response

    mock, _coroutine = get_mock_coro()
    mocker.patch('asyncio.sleep', _coroutine)

    await record_checker_instance.check_record(record_to_check)
    failed_msg = caplog.records[0].msg

    expected_msg = f'Sending metric record-checker-failed: {record_to_check}'
    assert failed_msg == expected_msg


@pytest.mark.asyncio
async def test_check_number_of_rrdata_is_not_equal(
        mocker, get_mock_coro,
        record_checker_instance, caplog,
        mock_resolve_query, dns_query_response):
    """Test that we fail on getting number of records
        from the srv which is not eqaule to the
        len of rrdata of our record """
    record_to_check = {
        "name": "ns1.dnsowl.com",
        "rrdatas": ["198.251.84.16", "173.254.242.221"],
        "type": "A",
        "ttl": 10686
    }

    mock_resolve_query.return_value = dns_query_response

    mock, _coroutine = get_mock_coro()
    mocker.patch('asyncio.sleep', _coroutine)

    await record_checker_instance.check_record(record_to_check)
    failed_msg = caplog.records[0].msg

    expected_msg = f'Sending metric record-checker-failed: {record_to_check}'
    assert expected_msg == failed_msg
