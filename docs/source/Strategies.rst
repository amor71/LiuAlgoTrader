.. _`Strategies`:

Strategies
==========

LiuAlgoTrader comes equipped with a **momentum** strategy,
which is based on `MACD signals`_ enforced with RSI_ and LOB imbalance signals.

.. _`MACD signals`:
    https://www.investopedia.com/terms/m/macd.asp

.. _RSI:
    https://www.investopedia.com/terms/r/rsi.asp

You can easily extend the available strategies,
by inheriting from the *Strategy* base class as explained below.

No Liability Disclaimer
-----------------------
The *momentum-strategy* is provided as a sample strategy,
You may choose to use it, modify it or completely
disregard it - LiuAlgoTrader and its authors bare
no responsibility to any possible loses from using
the strategy, or any other part of LiuAlgoTrader (on the other hand, they also won't
share your profits, if there are any).

Momentum Strategy
-----------------
Strategies are defined in the *tradeplan.toml* TOML
configuration file under the section:

.. code-block:: bash

    [[strategies]]

Note that several Strategies may run, yet the order
of execution is based the order presented in the *tradeplan* file.


The **[strategies.MomentumLong]** section lists the momentum strategy
properties:

+------------------+-----------------------------------------------+
| Name             | Description                                   |
+------------------+-----------------------------------------------+
| check_patterns   | Use candle-stick patterns for sell signals    |
|                  | this is false by default.                     |
+------------------+-----------------------------------------------+


The strategy (as any strategy you will develop
yourself) supports several execution windows under
the subsection

.. code-block:: bash

    [[strategies.MomentumLong.schedule]]

The schedule properties are:

+------------------+-----------------------------------------------+
| Name             | Description                                   |
+------------------+-----------------------------------------------+
| start            | The number of minutes, since start of the     |
|                  | trading day, to start buying and selling.     |
+------------------+-----------------------------------------------+
| duration         | The number of minutes, since the beginning of |
|                  | the strategy execution, to stop buying new    |
|                  | stock.                                        |
+------------------+-----------------------------------------------+

Custom Strategy
---------------
Creating your own custom strategy is as easy as
inheriting from the Strategy class, and implementing
the *run()* function which returns the selected stock symbols.

Here is an example of *my_strategy.py*:

.. code-block:: python

    from datetime import datetime, timedelta
    from typing import Dict, List, Tuple

    import alpaca_trade_api as tradeapi

    from pandas import DataFrame as df

    from liualgotrader.common import config
    from liualgotrader.common.tlog import tlog

    #
    # common.trading_data includes global variables, cross strategies that may be
    # helpful
    #
    from liualgotrader.common.trading_data import (buy_indicators, last_used_strategy,  open_orders,
                                                   sell_indicators, stop_prices, target_prices)


    from liualgotrader.strategies.base import Strategy

    #
    # TALIB is available is avaliable as part
    # of liualgotrader distribution
    # documentation can be found here https://www.ta-lib.org/
    # import talib
    # from talib import BBANDS, MACD, RSI


    class MyStrategy(Strategy):
        name = "MyStrategyForLosingMoney"

        def __init__(
            self,
            batch_id: str,
            schedule: List[Dict],
            ref_run_id: int = None,
            my_arg1: int = 0,
            my_arg2: bool = False,
        ):
            super().__init__(
                name=self.name,
                batch_id=batch_id,
                ref_run_id=ref_run_id,
                schedule=schedule,
            )
            self.my_arg1 = my_arg1
            self.my_arg2 = my_arg2

        async def buy_callback(self, symbol: str, price: float, qty: int) -> None:
            """
            This callback function is called by the trading frame work post
            completion of the buy ask. Partial fills won't trigger the callback,
            only the final complete will trigger this callback.
            """
            pass

        async def sell_callback(self, symbol: str, price: float, qty: int) -> None:
            """
            This callback function is called by the trading frame work post
            completion of the sell ask. Partial fills won't trigger the callback,
            only the final complete will trigger this callback.
            """
            pass

        async def create(self) -> None:
            """
            This function is called by the framework during the instantiation
            of the strategy. Keep in mind that running on multi-process environment
            it means that this function will be called at least once per spawned process.
            :return:
            """
            await super().create()
            tlog(f"strategy {self.name} created")


        async def run(
            self,
            symbol: str,
            position: int,
            minute_history: df,
            now: datetime,
            portfolio_value: float = None,
            trading_api: tradeapi = None,
            debug: bool = False,
            backtesting: bool = False,
        ) -> Tuple[bool, Dict]:
            """

            :param symbol: the symbol of the stock,
            :param position: the current held position,
            :param minute_history: DataFrame holding OLHC
                                   updated per *second*,
            :param now: current timestamp, specially important when called
                        from the backtester application,
            :param portfolio_value: your total porfolio value
            :param trading_api: the Alpca tradeapi, may either be
                                paper or live, depending on the
                                environment variable configurations,
            :param debug:       true / false, should be used mostly
                                for adding more verbosity.
            :param backtesting: true / false, which more are we running at
            :return: False w/ {} dictionary, or True w/ order execution
                     details (see below examples)
            """
            current_second_data = minute_history.iloc[-1]
            tlog(f"{symbol} data: {current_second_data}")

            morning_rush = (
                True if (now - config.market_open).seconds // 60 < 30 else False
            )
            if (
                await super().is_buy_time(now)
                and not position

            ):
                # Check for buy signals
                lbound = config.market_open
                ubound = lbound + timedelta(minutes=15)

                if debug:
                    tlog(f"15 schedule {lbound}/{ubound}")
                try:
                    high_15m = minute_history[lbound:ubound][  # type: ignore
                        "high"
                    ].max()
                    if debug:
                        tlog(f"{minute_history[lbound:ubound]}")  # type: ignore
                except Exception as e:
                    return False, {}

                if (
                    current_second_data.close > high_15m or config.bypass_market_schedule
                ):

                    #
                    # Global, cross strategies passed via the framework
                    #
                    target_prices[symbol] = 15.0
                    stop_prices[symbol] = 3.8

                    #
                    # indicators *should* be filled
                    #
                    buy_indicators[symbol] = {
                        "my_indicator": "random"
                    }

                    return (
                        True,
                        {
                            "side": "buy",
                            "qty": str(10),
                            "type": "limit",
                            "limit_price": "4.4"
                        }
                        if not morning_rush
                        else {
                            "side": "buy",
                            "qty": str(5),
                            "type": "market",
                        },
                    )
            if (
                await super().is_sell_time(now)
                and position > 0
                and last_used_strategy[symbol].name == self.name # important!
            ):
                # check if we already have open order
                if open_orders.get(symbol) is not None:
                    tlog(
                        f"{self.name}: open order for {symbol} exists, skipping"
                    )
                    return False, {}

                # Check for liquidation signals
                sell_indicators[symbol] = {
                    "my_indicator": "random"
                }

                tlog(
                    f"[{self.name}] Submitting sell for {position} shares of {symbol} at {current_second_data.close}"
                )
                return (
                    True,
                    {
                        "side": "sell",
                        "qty": str(position),
                        "type": "limit",
                        "limit_price": str(current_second_data.close),
                    },
                )

            return False, {}


Configuring the custom strategy in the *tradeplan* TOML file is as easy:

.. code-block:: bash

    # This is a TOML configuration file.

    # if set to true, allow running outside market open hours
    bypass_market_schedule = true

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
        [strategies.MyStrategy]
            filename = "examples/my_strategy.py"

            # check_patterns = true

            # trading schedules block, trades many have
            # several windows within the same day
            [[strategies.MyStrategy.schedule]]
                start = 15
                duration = 150

While executing, the **trader** application will look for *my_strategy.py*,
instantiate the `MyStrategy` class, and call it with the arguments defined
in the `tradeplan` configuration file, while adding the trade-api object.


Building a winning strategy
---------------------------

LiuAlgoTrader framework comes with a lot of tools
and capabilities which constantly evolve.
In order to write a winning strategy that
goes beyond the basic sample presented here,
it is best advised to go through the `under the hood`
section to understand how to re-use the framework
capabilities.

Hey, if you created an awesome strategy,
please share it with the rest of the community!











