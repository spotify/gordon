Configuring the Gordon Service
==============================


.. automodule:: gordon.main


Example Configuration
---------------------

An example of a ``gordon.toml`` file:

.. code-block:: ini

    [logging]
    level = "info"
    handlers = ["syslog"]


You may choose to have a ``gordon-user.toml`` file for development. Any top-level key will override what's found in ``gordon.toml``.

.. code-block:: ini

    [logging]
    level = "debug"
    handlers = ["stream"]


Supported Configuration
-----------------------

The following sections are supported:

logging
~~~~~~~

.. option:: level=info(default)|debug|warning|error|critical

    Any log level that is supported by the Python standard :py:mod:`logging` library.

.. option:: handlers=LIST-OF-STRINGS

    ``handlers`` support any of the following handlers: ``stream``, ``syslog``, and ``stackdriver``. Multiple handlers are supported. Defaults to ``syslog`` if none are defined.

    .. note::

        If ``stackdriver`` is selected, ``ulogger[stackdriver]`` needs to be installed as its dependencies are not installed by default.
