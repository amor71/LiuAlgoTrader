import time
from datetime import datetime, timedelta
from typing import List, Optional

import alpaca_trade_api as tradeapi
import requests
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog

from .base import Scanner


class Momentum(Scanner):
    name = "momentum"

    def __init__(
        self,
        provider: str,
        recurrence: Optional[timedelta],
        data_api: tradeapi,
        max_share_price: float,
        min_share_price: float,
        min_last_dv: float,
        today_change_percent: float,
        min_volume: float,
        from_market_open: float,
        max_symbols: int = config.total_tickers,
    ):
        self.provider = provider
        self.max_share_price = max_share_price
        self.min_share_price = min_share_price
        self.min_last_dv = min_last_dv
        self.min_volume = min_volume
        self.today_change_percent = today_change_percent
        self.from_market_open = from_market_open
        self.max_symbols = max_symbols

        super().__init__(
            name=self.name, recurrence=recurrence, data_api=data_api,
        )

    @classmethod
    def __str__(cls) -> str:
        return cls.name

    def _wait_time(self) -> None:
        if config.market_open:
            nyc = timezone("America/New_York")
            since_market_open = (
                datetime.today().astimezone(nyc) - config.market_open
            )

            if since_market_open.seconds // 60 < self.from_market_open:
                tlog(f"market open, wait {self.from_market_open} minutes")
                while since_market_open.seconds // 60 < self.from_market_open:
                    time.sleep(1)
                    since_market_open = (
                        datetime.today().astimezone(nyc) - config.market_open
                    )

        tlog(f"Scanner {self.name} ready to run")

    def _get_trade_able_symbols(self) -> List[str]:
        assets = self.data_api.list_assets()
        tlog(f"loaded list of {len(assets)} trade-able assets from Alpaca")

        trade_able_symbols = [
            asset.symbol for asset in assets if asset.tradable
        ]
        tlog(
            f"total number of trade-able symbols is {len(trade_able_symbols)}"
        )
        return trade_able_symbols

    def run_polygon(self) -> List[str]:
        tlog(f"{self.name}: run_polygon(): started")
        try:
            while True:
                tickers = self.data_api.polygon.all_tickers()
                tlog(f"loaded {len(tickers)} tickers from Polygon")
                if not len(tickers):
                    break
                trade_able_symbols = self._get_trade_able_symbols()

                unsorted = [
                    ticker
                    for ticker in tickers
                    if (
                        ticker.ticker in trade_able_symbols
                        and self.max_share_price
                        >= ticker.lastTrade["p"]
                        >= self.min_share_price
                        and ticker.prevDay["v"] * ticker.lastTrade["p"]
                        > self.min_last_dv
                        and ticker.todaysChangePerc
                        >= self.today_change_percent
                        and (
                            ticker.day["v"] > self.min_share_price
                            or config.bypass_market_schedule
                        )
                    )
                ]
                if len(unsorted) > 0:
                    ticker_by_volume = sorted(
                        unsorted,
                        key=lambda ticker: float(ticker.day["v"]),
                        reverse=True,
                    )
                    tlog(f"picked {len(ticker_by_volume)} symbols")
                    return [x.ticker for x in ticker_by_volume][
                        : self.max_symbols
                    ]

                tlog("did not find gaping stock, retrying")
                time.sleep(30)
        except KeyboardInterrupt:
            tlog("KeyboardInterrupt")
            pass

        return []

    def run_finnhub(self) -> List[str]:
        tlog(f"{self.name}: run_finnhub(): started")
        trade_able_symbols = self._get_trade_able_symbols()

        nyc = timezone("America/New_York")
        _from = datetime.today().astimezone(nyc) - timedelta(days=1)
        _to = datetime.now(nyc)
        symbols = []
        try:
            with requests.Session() as s:
                for symbol in trade_able_symbols:
                    try:
                        retry = True
                        while retry:
                            retry = False
                            url = (
                                f"{config.finnhub_base_url}/stock/candle?symbol={symbol}&"
                                f"resolution=D&from={_from.strftime('%s')}&to={_to.strftime('%s')}&"
                                f"token={config.finnhub_api_key}"
                            )

                            try:
                                r = s.get(url)
                            except ConnectionError:
                                retry = True
                                continue

                            if r.status_code == 200:
                                response = r.json()
                            if response["s"] != "no_data":
                                prev_prec = (
                                    100.0
                                    * (response["c"][1] - response["c"][0])
                                    / response["c"][0]
                                )
                                if (
                                    self.max_share_price
                                    > response["c"][1]
                                    > self.min_share_price
                                    and response["v"][0] * response["c"][0]
                                    > self.min_last_dv
                                    and prev_prec > self.today_change_percent
                                    and response["v"][1] > self.min_volume
                                ):
                                    symbols.append(symbol)
                                    tlog(
                                        f"collected {len(symbols)}/{self.max_symbols}"
                                    )
                                    if len(symbols) == self.max_symbols:
                                        break

                            elif r.status_code == 429:
                                tlog(
                                    f"{trade_able_symbols.index(symbol)}/{len(trade_able_symbols)} API limit: ({r.text})"
                                )
                                time.sleep(30)
                                retry = True
                            else:
                                print(r.status_code, r.text)

                    except IndexError:
                        pass

        except KeyboardInterrupt:
            tlog("KeyboardInterrupt")
            pass

        tlog(f"loaded {len(symbols)} from Finnhub")
        return symbols

    def run(self) -> List[str]:
        self._wait_time()

        if self.provider == "polygon":
            return self.run_polygon()
        elif self.provider == "finnhub":
            return self.run_finnhub()
        else:
            raise Exception(
                f"Invalid provider {self.provider} for scanner {self.name}"
            )
