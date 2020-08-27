.. _`How to Configure`:

How to Configure
================

There are two parts to configuration the **trader**
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

.. code-block:: bash

    #!/bin/bash
    set -e

    # used for paper-trading accounts
    export ALPACA_PAPER_BASEURL=
    export ALPACA_PAPER_API_KEY=
    export ALPACA_PAPER_API_SECRET=

    # used for data-feeds, and live trading
    export ALPACA_LIVE_BASEURL=
    export ALPACA_LIVE_API_KEY=
    export ALPACA_LIVE_API_SECRET=

    # database connectivity
    export DSN="postgresql://momentum@localhost/tradedb"

    # used by Analysis notebooks
    export APCA_API_KEY_ID=
    export APCA_API_SECRET_KEY=

    export FINNHUB_API_KEY=
    export FINNHUB_BASE_URL=

    export LIU_MAX_SYMBOLS=440

TOML configuration file
-----------------------
the **trader** application expects a TOML configuration file.
Press here_ to learn more on the TOML file format.

.. _here: https://toml.io/en/

by default the trader application will be looking for
a configuration file with the name *tradeplan.toml*.
The configuration file, as it's name implies,
defines the trade-plan for the trader execution:
it defines which stock-scanners to use,
and which algorithmic strategies to applied on the
selected stocks.

Following is a TOML trading sample file,
see Scanner and Strategies section respectively
to learn more on the available tools, and how to extend
them with your own.

.. code-block:: none

    # This is a TOML configuration file.

    # if set to true, allow running outside market open hours
    bypass_market_schedule = false

    # ticket scanners, may have several
    # scanners during the day
    [[scanners]]
        [scanners.momentum]
            # check documentation for supported providers
            provider = 'polygon'

            # scan for tickers with minimal volume since day start
            min_volume = 30000

            # minimum daily percentage gap
            min_gap = 3.5

            # minimum last day dollar volume
            min_last_dv = 500000

            min_share_price = 2.0
            max_share_price = 20.0

            # How many minutes from market open, to start running scanner
            from_market_open = 15

            # recurrence = 5

            # max_symbols = 440

    # trading strategies, can have several *strategy* blocks
    [[strategies]]

        # strategy class name, must implement Strategy class
        [strategies.MomentumLong]
        # strategy file
        filename = "strategies/momentum_long.py"

        # trading schedules block, trades many have
        # several windows within the same day
        [[strategies.MomentumLong.schedule]]
            start = 15
            duration = 150



