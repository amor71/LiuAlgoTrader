Configuration
=============

There are two parts of configuration for the **trader**
application: OS level environment variables,
and TOML configuration file read by the trader application.

Environment variables
---------------------

Environment variables are used to configure authentication
to external resources, such as the trading database,
broker access and more.

Authentication details should be kept separate from the rest
of the execution code & configuration to have better protection
as well as support dockerized executions.

Below is an example of a configuration variables script,
which is not kept in the repository:

.. literalinclude:: ../../examples/env_vars.sh
  :language: bash
  :linenos:

Additional parameters
*********************

LiuAlgoTrader is a multi-processing framework with
producer-consumers design pattern. There is a
process for interacting with the data-stream
providers (e.g `Polygon.io`), a process for scanning
& picking stocks, and other processes specific to consumers.

The number of consumer processes depends on the number of CPU cores, load average and a
multiplication factor. The default multiplication
factor is **2.0** by default. However it is possible to
override this by the environment variable
`CPU_FACTOR`. If you notice that the load average
of your system is quite low when running the `trader`
application it's recommended to increase the number (depending on the complexity of your
strategies). If the load of the system is too high, it is recommended to lower the number.

It is also possible to by-pass `LiuAlgoTrader`
calculation of optimal number of processes, and
use a pre-defined number of consumer processes.
To do so you can assign a positive integer
to the environment variable `NUM_CONSUMERS`.

`TRADEPLAN_DIR` specifies the location of
the `tradeplan.toml` configuration file.
It's used by both the `trader` and `backtester`
applications.

TOML configuration file
-----------------------
the **trader** & **backtester** applications expect a TOML configuration file.
Click here_ to learn more on the TOML file format.

.. _here: https://toml.io/en/

By default the trader application will be looking for
a configuration file with the name *tradeplan.toml*.
The configuration file, as it's name implies,
defines the trade-plan for the trader execution:
it defines which stock-scanners to use,
and which algorithmic strategies to applied on the
selected stocks.

Following is a sample of TOML configuration file.
See Scanner and Strategies section respectively
to learn more on the available tools, and how to extend
them.

.. literalinclude:: ../../examples/tradeplan.toml
  :language: bash
  :linenos:
