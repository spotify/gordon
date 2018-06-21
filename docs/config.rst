Configuring the Gordon Service
==============================


.. automodule:: gordon.main


Example Configuration
---------------------

An example of a ``gordon.toml`` file:

.. literalinclude:: ../gordon.toml.example
    :language: ini


You may choose to have a ``gordon-user.toml`` file for development. Any top-level key will override what's found in ``gordon.toml``.

.. code-block:: ini

    [core]
    debug = true

    [core.logging]
    level = "debug"
    handlers = ["stream"]


Supported Configuration
-----------------------

The following sections are supported:

core
~~~~

.. option:: plugins=LIST-OF-STRINGS

    Plugins that the Gordon service needs to load. If a plugin is not listed, Gordon will skip it even if there's configuration.

    The strings must match the plugin's config key. See the plugin's documentation for config key names.

.. option:: debug=true|false

    Whether or not to run the Gordon service in ``debug`` mode.

    If ``true``, Gordon will continue running even if installed & configured plugins can not be loaded. Plugin exceptions will be logged as warnings with tracebacks.

    If ``false``, Gordon will exit out if it can't load one or more plugins.

.. option:: metrics=STR

    The metrics provider to use. Depending on the provider, more
    configuration may be needed. See provider implementation for details.


core.logging
~~~~~~~~~~~~

.. option:: level=info(default)|debug|warning|error|critical

    Any log level that is supported by the Python standard :py:mod:`logging` library.

.. option:: handlers=LIST-OF-STRINGS

    ``handlers`` support any of the following handlers: ``stream``, ``syslog``, and ``stackdriver``. Multiple handlers are supported. Defaults to ``syslog`` if none are defined.

    .. note::

        If ``stackdriver`` is selected, ``ulogger[stackdriver]`` needs to be installed as its dependencies are not installed by default.

Other key-value pairs as supported by `ulogger`_ will be passed into the configured handlers. For example:

.. code-block:: ini

    [core.logging]
    level = "info"
    handlers = ["syslog"]
    address = ["10.99.0.1", "514"]
    format = "%(created)f %(levelno)d %(message)s"
    date_format = "%Y-%m-%dT%H:%M:%S"


core.route
~~~~~~~~~~
A table of key-value pairs of phases used to indicate the route the
a message should take. All keys should correspond to either
the `start_phase` attribute of a runnable plugin or the `phase` of a message
handling plugin. Values may only correspond to `phase` of a message handling
plugin.

.. code-block:: ini

    [core.route]
    start_phase = "phase2"
    phase2 = "phase3"


.. _`ulogger`: https://github.com/spotify/ulogger
