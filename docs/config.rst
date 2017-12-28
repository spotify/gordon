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


core.logging
~~~~~~~~~~~~

.. option:: level=info(default)|debug|warning|error|critical

    Any log level that is supported by the Python standard :py:mod:`logging` library.

.. option:: handlers=LIST-OF-STRINGS

    ``handlers`` support any of the following handlers: ``stream``, ``syslog``, and ``stackdriver``. Multiple handlers are supported. Defaults to ``syslog`` if none are defined.

    .. note::

        If ``stackdriver`` is selected, ``ulogger[stackdriver]`` needs to be installed as its dependencies are not installed by default.