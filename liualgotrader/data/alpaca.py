import asyncio
import queue
import sys
import time
import traceback
from datetime import date, datetime, timedelta
from random import randint
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import pandas_market_calendars
import pytz
import requests
from alpaca_trade_api.rest import REST, URL, APIError, TimeFrame
from alpaca_trade_api.stream import Stream

from liualgotrader.common import config
from liualgotrader.common.list_utils import chunks
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import QueueMapper, TimeScale, WSEventType
from liualgotrader.data.data_base import DataAPI
from liualgotrader.data.streaming_base import StreamingAPI

NY = "America/New_York"
nytz = pytz.timezone(NY)


class AlpacaData(DataAPI):
    def __init__(self):
        self.alpaca_rest_client = REST(
            key_id=config.alpaca_api_key, secret_key=config.alpaca_api_secret
        )
        if not self.alpaca_rest_client:
            raise AssertionError(
                "Failed to authenticate Alpaca RESTful client"
            )

        self.datetime_cache: Dict[datetime, datetime] = {}

    def get_symbols(self) -> List[Dict]:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        return self.alpaca_rest_client.list_assets()

    def _localize_start_end(self, start: date, end: date) -> Tuple[str, str]:
        return (
            nytz.localize(
                datetime.combine(start, datetime.min.time())
            ).isoformat(),
            (
                nytz.localize(
                    datetime.now().replace(microsecond=0)
                ).isoformat()
                if end >= date.today()
                else nytz.localize(
                    datetime.combine(end, datetime.min.time())
                ).isoformat()
            ),
        )

    def get_last_trading(self, symbol: str) -> datetime:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        try:
            snapshot_data = self.alpaca_rest_client.get_snapshot(symbol)
        except APIError:
            raise ValueError(f"{symbol} snapshot not found")

        min_bar = snapshot_data.minute_bar
        if not min_bar:
            raise ValueError(f"Can't get snapshot for {symbol}")

        return min_bar.t

    def get_trading_holidays(self) -> List[str]:
        nyse = pandas_market_calendars.get_calendar("NYSE")
        return nyse.holidays().holidays

    def get_trading_day(self, now: datetime, offset: int) -> datetime:
        cbd_offset = pd.tseries.offsets.CustomBusinessDay(
            n=offset, holidays=self.get_trading_holidays()
        )

        return nytz.localize(now + cbd_offset)

    def num_trading_minutes(self, start: date, end: date) -> int:
        # Alpaca extended trading data is from 4AM to 8PM
        return (20 - 4) * 60

    def num_trading_days(self, start: date, end: date) -> int:
        return len(
            pd.date_range(
                start,
                end,
                freq=pd.tseries.offsets.CustomBusinessDay(
                    holidays=self.get_trading_holidays()
                ),
            )
        )

    def get_max_data_points_per_load(self) -> int:
        # Alpaca suggests 10000 points
        return 10000

    def _is_crypto_symbol(self, symbol: str) -> bool:
        return symbol.lower() in ["btcusd", "ethusd"]

    def trading_days_slice(self, s: slice) -> slice:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        if s.start in self.datetime_cache and s.stop in self.datetime_cache:
            return slice(
                self.datetime_cache[s.start], self.datetime_cache[s.stop]
            )

        trading_days = self.alpaca_rest_client.get_calendar(
            str(s.start.date()), str(s.stop.date())
        )
        new_slice = slice(
            nytz.localize(
                datetime.combine(
                    trading_days[0].date.date(), trading_days[0].open
                )
            ),
            nytz.localize(
                datetime.combine(
                    trading_days[-1].date.date(), trading_days[-1].open
                )
            ),
        )

        self.datetime_cache[s.start] = new_slice.start
        self.datetime_cache[s.stop] = new_slice.stop

        return new_slice

    def crypto_get_symbol_data(
        self,
        symbol: str,
        start: str,
        end: str,
        timeframe: TimeFrame,
    ) -> pd.DataFrame:
        url = f"{config.alpaca_crypto_base_url}/{symbol}/bars"
        response = requests.get(
            url,
            params={  # type:ignore
                "start": start,
                "end": end,
                "limit": 10000,
                "timeframe": "1Day" if timeframe == TimeFrame.Day else "1Min",
            },
            headers={
                "APCA-API-KEY-ID": config.alpaca_api_key,
                "APCA-API-SECRET-KEY": config.alpaca_api_secret,
            },
        )
        if response.status_code == 200:
            df = pd.DataFrame(response.json()["bars"])
            df.rename(
                columns={
                    "o": "open",
                    "c": "close",
                    "h": "high",
                    "l": "low",
                    "v": "volume",
                    "vw": "average",
                    "t": "timestamp",
                },
                inplace=True,
            )
            df["timestamp"] = pd.to_datetime(df.timestamp)
            df["trade_count"] = np.NaN
            df["vwap"] = np.NaN
            df = df.set_index(df.timestamp)
            df = df[~df.index.duplicated(keep="first")]
            return df

        raise ValueError(
            f"ALPACA CRYPTO {response.status_code} {response.text}"
        )

    def get_symbols_data(
        self,
        symbols: List[str],
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> Dict[str, pd.DataFrame]:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")
        if not isinstance(symbols, list):
            raise AssertionError(f"{symbols} must be a list")

        if scale == TimeScale.minute:
            end += timedelta(days=1)
        _start, _end = self._localize_start_end(start, end)
        dfs: Dict = {}
        t: TimeFrame = (
            TimeFrame.Minute
            if scale == TimeScale.minute
            else TimeFrame.Day
            if scale == TimeScale.day
            else None
        )
        try:
            data = self.alpaca_rest_client.get_bars(
                symbol=symbols,
                timeframe=t,
                start=_start,
                end=_end,
                limit=1000000000,
                adjustment="all",
            ).df
        except requests.exceptions.HTTPError as e:
            tlog(f"received HTTPError: {e}")
            if e.response.status_code in (500, 502, 504, 429):
                tlog("retrying")
                time.sleep(10)
                return self.get_symbols_data(symbols, start, end, scale)

        data = data.tz_convert("America/New_York")
        data["average"] = data.vwap
        data["count"] = data.trade_count
        data["vwap"] = np.NaN
        grouped = data.groupby(data.symbol)
        for symbol in data.symbol.unique():
            dfs[symbol] = grouped.get_group(symbol)[
                [
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "count",
                    "average",
                    "vwap",
                ]
            ]

        return dfs

    def get_symbol_data(
        self,
        symbol: str,
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> pd.DataFrame:
        _start, _end = self._localize_start_end(start, end)

        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        t: TimeFrame = (
            TimeFrame.Minute
            if scale == TimeScale.minute
            else TimeFrame.Day
            if scale == TimeScale.day
            else None
        )

        try:
            data = (
                self.alpaca_rest_client.get_bars(
                    symbol=symbol,
                    timeframe=t,
                    start=_start,
                    end=_end,
                    limit=1000000,
                    adjustment="all",
                ).df
                if not self._is_crypto_symbol(symbol)
                else self.crypto_get_symbol_data(
                    symbol=symbol, start=_start, end=_end, timeframe=t
                )
            )
        except requests.exceptions.HTTPError as e:
            tlog(f"received HTTPError: {e}")
            if e.response.status_code in (500, 502, 504, 429):
                tlog("retrying")
                time.sleep(10)
                return self.get_symbol_data(symbol, start, end, scale)

        except Exception as e:
            raise ValueError(
                f"[EXCEPTION] {e} for {symbol} has no data for {_start} to {_end} w {scale.name}"
            )
        else:
            if data.empty:
                raise ValueError(
                    f"[ERROR] {symbol} has no data for {_start} to {_end} w {scale.name}"
                )

        data.index = data.index.tz_convert("America/New_York")
        data["average"] = data.vwap
        data["count"] = data.trade_count
        data["vwap"] = np.NaN

        return data[
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "count",
                "average",
                "vwap",
            ]
        ]


class AlpacaStream(StreamingAPI):
    def __init__(self, queues: QueueMapper):
        self.alpaca_ws_client = Stream(
            base_url=URL(config.alpaca_base_url),
            key_id=config.alpaca_api_key,
            secret_key=config.alpaca_api_secret,
            data_feed=config.alpaca_data_feed,
        )

        if not self.alpaca_ws_client:
            raise AssertionError(
                "Failed to authenticate Alpaca web_socket client"
            )

        self.running = False
        super().__init__(queues)

    async def run(self):
        if not self.running:
            if not self.queues:
                raise AssertionError(
                    "can't call `AlpacaStream.run()` without queues"
                )

            asyncio.create_task(self.alpaca_ws_client._run_forever())
            self.running = True

    @classmethod
    async def bar_handler(cls, msg):
        try:
            event = {
                "symbol": msg.symbol,
                "open": msg.open,
                "close": msg.close,
                "high": msg.high,
                "low": msg.low,
                "timestamp": pd.to_datetime(
                    msg.timestamp, utc=True
                ).astimezone(nytz),
                "volume": msg.volume,
                "count": msg.trade_count,
                "vwap": None,
                "average": msg.vwap,
                "totalvolume": None,
                "EV": "AM",
            }
            cls.get_instance().queues[msg.symbol].put(event, timeout=1)
        except queue.Full as f:
            tlog(
                f"[EXCEPTION] process_message(): queue for {event['sym']} is FULL:{f}"
            )
            raise
        except Exception as e:
            tlog(
                f"[EXCEPTION] process_message(): exception of type {type(e).__name__} with args {e.args}"
            )
            if config.debug_enabled:
                traceback.print_exc()

    @classmethod
    async def trades_handler(cls, msg):
        try:
            ts = pd.to_datetime(msg.timestamp)
            if (time_diff := (datetime.now(tz=nytz) - ts)) > timedelta(
                seconds=10
            ) and randint(  # nosec
                1, 100
            ) == 1:  # nosec
                tlog(
                    f"Received trade for {msg.symbol} too out of sync w {time_diff}"
                )

            event = {
                "symbol": msg.symbol,
                "price": msg.price,
                "open": msg.price,
                "close": msg.price,
                "high": msg.price,
                "low": msg.price,
                "timestamp": ts,
                "volume": msg.size,
                "exchange": msg.exchange,
                "conditions": msg.conditions,
                "tape": msg.tape,
                "average": None,
                "count": 1,
                "vwap": None,
                "EV": "T",
            }

            cls.get_instance().queues[msg.symbol].put(event, block=False)

        except queue.Full as f:
            tlog(
                f"[EXCEPTION] process_message(): queue for {event['sym']} is FULL:{f}"
            )
            raise
        except Exception as e:
            tlog(
                f"[EXCEPTION] process_message(): exception of type {type(e).__name__} with args {e.args}"
            )
            if config.debug_enabled:
                traceback.print_exc()

    @classmethod
    async def quotes_handler(cls, msg):
        print(f"quotes_handler:{msg}")

    async def subscribe(
        self, symbols: List[str], events: List[WSEventType]
    ) -> bool:
        tlog(f"Starting subscription for {len(symbols)} symbols")
        upper_symbols = [symbol.upper() for symbol in symbols]
        for syms in chunks(upper_symbols, 1000):
            tlog(f"\tsubscribe {len(syms)}/{len(upper_symbols)}")
            for event in events:
                if event == WSEventType.SEC_AGG:
                    tlog(f"event {event} not implemented in Alpaca")
                elif event == WSEventType.MIN_AGG:
                    self.alpaca_ws_client._data_ws._running = False
                    self.alpaca_ws_client.subscribe_bars(
                        AlpacaStream.bar_handler, *syms
                    )
                elif event == WSEventType.TRADE:
                    self.alpaca_ws_client.subscribe_trades(
                        AlpacaStream.trades_handler, *syms
                    )
                elif event == WSEventType.QUOTE:
                    self.alpaca_ws_client.subscribe_quotes(
                        AlpacaStream.quotes_handler, *syms
                    )

            await asyncio.sleep(1)

        tlog(f"Completed subscription for {len(symbols)} symbols")
        return True
