# -*- coding: utf-8 -*-
# Copyright (c) 2017 Spotify AB
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


class GordonError(Exception):
    """General Gordon Application Error."""


class LoadPluginError(GordonError):
    """Error loading plugin."""


class InvalidDNSHost(GordonError):
    """Error when given invalid DNS server to query."""


class MissingPluginError(GordonError):
    """Missing a required plugin."""


class InvalidPluginError(GordonError):
    """Plugin implementation is invalid."""
