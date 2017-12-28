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

import json
import os
from pathlib import Path

import jsonschema


from gordon import exceptions

DEF_DIR = Path(os.path.dirname(__file__), 'definitions').absolute()


class JsonValidator(object):

    def __init__(self):
        """Initialize known schemas from files into reference dict."""
        self.schemas = {}
        for jsonfile in DEF_DIR.glob('*.json'):
            with open(jsonfile) as definition:
                self.schemas[jsonfile.stem] = json.loads(definition.read())

    def validate(self, json_dict, schema):
        """Validate supplied JSON object against a known schema.

        Args:
            json_dict (dict): a dict representation of the JSON object
            schema (str): name of the schema

        Raises:
            GordonJsonValidationError if JSON is invalid or cannot be validated
        """
        try:
            jsonschema.validate(json_dict, self.schemas[schema])
            return
        except KeyError:
            err = f'Schema not found (available: {list(self.schemas)})'
        except jsonschema.ValidationError as e:
            err = f'JSON schema was invalid: {e}'
        raise exceptions.GordonJsonValidationError(err)
