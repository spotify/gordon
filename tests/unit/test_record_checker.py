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

from gordon import exceptions, record_checker


#####
# Tests & fixtures for running record checker
#####

@pytest.fixture
def record_checker_instance():
    dns_ip = '8.8.8.8'
    return record_checker.RecordChecker(dns_ip)


@pytest.fixture
def record_1(mocker):
    record_mock = mocker.Mock(Record)
    record_mock.qtype = 1
    record_mock.name = 'example.com'
    record_mock.data = '127.1.1.1'
    record_mock.ttl = 10686
    return record_mock


@pytest.fixture
def record_2(record_1):
    record_1.data = '127.1.1.2'
    return record_1


@pytest.fixture
def record_3(record_1):
    record_1.data = '127.1.1.3'
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
    mocker.patch.object(record_checker_instance._resolver, 'query', _coroutine)
    return mock


@pytest.mark.asyncio
async def test_check_time_on_success(
        record_checker_instance, caplog,
        mock_resolve_query, dns_query_response):
    """Test the time it took to check a record is in expected range"""
    record_to_check = {
        'name': 'example.com',
        'rrdatas': ['127.1.1.1', '127.1.1.2', '127.1.1.3'],
        'type': 'A',
        'ttl': 10686
    }

    mock_resolve_query.return_value = dns_query_response

    await record_checker_instance.check_record(record_to_check)

    success_msg = caplog.records[0].msg

    time_it_took_to_check_record = \
        float(success_msg.split('took ')[1].split(' to')[0])

    max_time_to_sleep_when_success = 6

    assert 0 < time_it_took_to_check_record < max_time_to_sleep_when_success


@pytest.mark.asyncio
async def test_check_record_failure_ttl_not_equal(
        mocker, get_mock_coro,
        record_checker_instance, caplog,
        mock_resolve_query, dns_query_response):
    """Test failure timeout.

    The failure happens because the ttl is not equal.
    """
    record_to_check = {
        'name': 'example.com',
        'rrdatas': ['127.1.1.1', '127.1.1.2', '127.1.1.3'],
        'type': 'A',
        'ttl': 1068
    }

    mock_resolve_query.return_value = dns_query_response

    mock, _coroutine = get_mock_coro()
    mocker.patch('asyncio.sleep', _coroutine)

    await record_checker_instance.check_record(record_to_check)
    actual_msg = caplog.records[0].msg

    expected_msg = f'Sending metric record-checker-failed: {record_to_check}.'
    assert expected_msg == actual_msg


@pytest.mark.asyncio
async def test_length_of_rrdata_is_not_equal(
        mocker, get_mock_coro,
        record_checker_instance, caplog,
        mock_resolve_query, dns_query_response):
    """Test failure timeout.

    The failure happens because the length of
        rrdatas list is not equal.
    """
    record_to_check = {
        'name': 'example.com',
        'rrdatas': ['127.1.1.1', '127.1.1.2'],
        'type': 'A',
        'ttl': 10686
    }

    mock_resolve_query.return_value = dns_query_response

    mock, _coroutine = get_mock_coro()
    mocker.patch('asyncio.sleep', _coroutine)

    await record_checker_instance.check_record(record_to_check)
    actual_msg = caplog.records[0].msg

    expected_msg = f'Sending metric record-checker-failed: {record_to_check}.'
    assert expected_msg == actual_msg


@pytest.mark.asyncio
async def test_proxy_resolver_failure():
    """Test record checker got invalid dns ip"""
    dns_ip = '8.855.0.5'

    with pytest.raises(exceptions.InvalidDNSHost) as e:
        record_checker.RecordChecker(dns_ip)

    expected_msg = 'RecordChecker got invalid DNS server IP: 8.855.0.5.'
    assert e.match(expected_msg)
