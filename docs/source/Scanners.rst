.. _`Scanners`:

Scanners
========

LiuAlgoTrader comes equipped with a **momentum** scanner,
which is best used shortly after the start of the
trading day and identifies trending stocks that
adhere to certain restrictions.

You can easily extend the available scanners,
by inheriting from the *Scanner* base class
in order to select specific stocks, or apply different
stock selection logic that fit your needs.

Momentum Scanner
----------------
Scanners are defined in the *tradeplan.toml* TOML
configuration file under the section **[[scanners]]**. Note that
several Scanners may run, at different schedules and
identify new stocks that needs to be fed into the Strategies
pipeline.

The **[scanners.momentum]** momentum scanner has several
properties:

+------------------+-----------------------------------------------+
| Name             | Description                                   |
+------------------+-----------------------------------------------+
| provider         | stock data provider: *polygon*, *finnhub*     |
+------------------+------------------------+----------------------+
| min_volume       | scan for tickers with minimal volume since    |
|                  | day start                                     |
+------------------+-----------------------------------------------+
| min_gap          | tickers gaping up in percentage (e.g. 3.5)    |
+------------------+-----------------------------------------------+
| min_last_dv      | minimum last day dollar x volume              |
+------------------+-----------------------------------------------+
| min_share_price  | minimum stock price                           |
+------------------+-----------------------------------------------+
| max_share_price  | maximum stock price                           |
+------------------+-----------------------------------------------+
| from_market_open | number of minutes to wait, since market open  |
|                  | before starting to scan from relevant stocks  |
+------------------+-----------------------------------------------+
| max_symbols      | max number of symbols to scan for             |
+------------------+-----------------------------------------------+
| recurrence       | frequency of re-running scanner, if not       |
|                  | present, run only once                        |
+------------------+-----------------------------------------------+

**Notes**

- When using Finnhub, since there is currently no way to get a full view of the market, it's best advised to use the max_symbols property, at lower numbers, unless you have access to a paid Finnhub account without API throttling.
- Unless otherwise specified, the trader applications scans & trades a limited number of stocks, however that limitation may be overwritten using **LIU_MAX_SYMBOLS** env variable.

Custom Scanner
--------------
Creating your own custom scanner is as easy as inheriting from the Scanner class,
and implementing the *run()* function which returns the selected stock symbols.

Here is an example of *my_scanner.py*:

.. literalinclude:: ../../examples/scanners/my_scanner.py
  :language: python
  :linenos:


Configuring the custom scanner in the *tradeplan* TOML file is as easy:

.. code-block:: none

    [scanners]
        [scanners.MyScanner]
            filename = "my_scanner.py"

            my_arg1 = 30000
            my_arg2 = 3.5

While executing, the **trader** application will look for *my_scanner.py*,
instantiate the `MyScaner` class, and call it with the arguments defined
in the `tradeplan` configuration file, while adding the trade-api object.

Scanners in back-test application
*********************************

The scanners `run()` function receives a datetime
parameter **back_time**. The parameter is used when
called from the backtester when the
"`back-test against the whole day`" option is used.

Scanners are expected to support this mode by querying
past data from the data (if such exists).
Sample_ implementation can be found

.. _Sample:
    https://github.com/amor71/LiuAlgoTrader/blob/master/liualgotrader/scanners/momentum.py#L270


Sending picks to a specific strategy
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Starting from release 0.0.50, it is possible f
or scanners to direct picked stocks to specific
strategies. using the configuration parameter
`target_strategy_name` the scanner can be
directed which Strategy.name to direct the picks
for. Unless specified, all running strategies
will be delivered new picks.

.. code-block:: none

    [scanners]
        [scanners.MyScanner]
            filename = "my_scanner.py"

            my_arg1 = 30000
            my_arg2 = 3.5
            target_strategy_name = "golden_pair"