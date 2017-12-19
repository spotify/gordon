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

from gordon import exceptions
from gordon.schema.validate import JsonValidator


@pytest.fixture(scope='session')
def validator():
    return JsonValidator()


valid_audit_log = {
    'methodName': 'v1.compute.instances.insert',
    'resourceName': '/projects/project-a/zones/zone-b/instances/vm-abc'
}
valid_record_a = {
    'name': 'test1-hostname-a1.subdomain.example.com',
    'target': '10.0.0.1'
}
valid_record_cname = {
    'name': 'some_domain.example.com',
    'target': 'some_other_name.somewhere.else.com',
    'type': 'CNAME',
    'action': 'create'
}


@pytest.mark.parametrize('valid_json,name', [
    (valid_audit_log, 'google-audit-log'),
    (valid_record_a, 'record-action'),
    (valid_record_cname, 'record-action')
])
def test_json_validator_success(validator, valid_json, name):
    """Validates against multiple valid inputs."""
    # No need to assert, since exception will raise on failure
    validator.validate(valid_json, name)


@pytest.mark.parametrize('invalid_json', [{'bad': 'json'}, '{"bad": "dict"}'])
def test_json_validator_raises_on_invalid_data(validator, invalid_json):
    """Raise exception when supplied with anything that doesn't match schema."""
    with pytest.raises(exceptions.GordonJsonValidationError) as e:
        assert validator.validate(invalid_json, 'record-action')
    assert 'JSON schema was invalid' in str(e.value)


def test_json_validator_raises_on_schema_not_found(validator):
    """Raise exception when attempting validation against unknown schema."""
    with pytest.raises(exceptions.GordonJsonValidationError) as e:
        assert validator.validate({}, 'fake-schema-name')
    expected = f'Schema not found (available: {list(validator.schemas)})'
    assert expected == str(e.value)
