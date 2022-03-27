import asyncio
import concurrent.futures
import queue
import time
import traceback
from datetime import date, datetime, timedelta
from random import randint
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pandas_market_calendars
import pytz
import requests
from alpaca_trade_api.rest import REST, URL, APIError, TimeFrame
from alpaca_trade_api.stream import Stream
from dateutil.parser import parse as date_parser

from liualgotrader.common import config
from liualgotrader.common.list_utils import chunks
from liualgotrader.common.tlog import tlog, tlog_exception
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
        # for requesting market snapshots by chunk of symbols
        self.symbol_chunk_size = 1000
        self.datetime_cache: Dict[datetime, datetime] = {}

    def get_symbols(self) -> List[str]:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        return [
            asset.symbol
            for asset in self.alpaca_rest_client.list_assets(
                status="active", asset_class="us_equity"
            )
            if asset.tradable
        ]

    def get_market_snapshot(
        self, filter_func: Optional[Callable] = None
    ) -> List[Dict]:
        # parse market snapshots per chunk of symbols
        symbols = self.get_symbols()
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(
            self._get_symbols_snapshot(symbols, filter_func)
        )

    async def _get_symbols_snapshot(
        self, symbols: List[str], filter_func: Optional[Callable]
    ) -> List[Dict]:
        def _parse_ticker_snapshot(_ticker: str, _ticket_snapshot: object):
            try:
                return {
                    "ticker": _ticker,
                    **{
                        sub_snapshot_type: _sub_snapshot_obj.__dict__["_raw"]
                        for sub_snapshot_type, _sub_snapshot_obj in _ticket_snapshot.__dict__.items()
                    },
                }
            # skip over if some snapshot type is missing (e.g. "prev_daily_bar": None)
            except AttributeError:
                return None

        def _parse_snapshot_and_filter(_symbols: List[str]) -> List[Dict]:
            processed_tickers_snapshot = map(
                lambda key_and_val: _parse_ticker_snapshot(*key_and_val),
                self.alpaca_rest_client.get_snapshots(_symbols).items(),
            )
            return list(
                filter(
                    lambda snapshot: (
                        (snapshot is not None) and (filter_func(snapshot))  # type: ignore
                    ),
                    list(processed_tickers_snapshot),  # type : ignore
                )
                if filter_func is not None
                else processed_tickers_snapshot
            )

        # request snapshots per chunk of tickers by concurrency
        with concurrent.futures.ThreadPoolExecutor() as executor:
            loop = asyncio.get_event_loop()
            futures = [
                loop.run_in_executor(
                    executor,
                    _parse_snapshot_and_filter,
                    symbols[symbol_idx : symbol_idx + self.symbol_chunk_size],
                )
                for symbol_idx in range(
                    0, len(symbols), self.symbol_chunk_size
                )
            ]

            market_snapshots = [
                y for x in await asyncio.gather(*futures) for y in x
            ]

        return market_snapshots

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

        if self._is_crypto_symbol(symbol):
            return datetime.now(tz=nytz)
        try:
            snapshot_data = self.alpaca_rest_client.get_snapshot(symbol)
        except APIError:
            raise ValueError(f"{symbol} snapshot not found")

        min_bar = snapshot_data.latest_trade
        if not min_bar:
            raise ValueError(f"Can't get snapshot for {symbol}")

        return min_bar.t

    def get_trading_holidays(self) -> List[str]:
        nyse = pandas_market_calendars.get_calendar("NYSE")
        return nyse.holidays().holidays

    def get_trading_day(
        self, symbol: str, now: datetime, offset: int
    ) -> datetime:
        if self._is_crypto_symbol(symbol):
            cbd_offset = timedelta(days=offset)
        else:
            cbd_offset = pd.tseries.offsets.CustomBusinessDay(
                n=offset - 1, holidays=self.get_trading_holidays()
            )

        return nytz.localize(now + cbd_offset)

    def num_trading_minutes(self, symbol: str, start: date, end: date) -> int:
        return (24 if self._is_crypto_symbol(symbol) else (20 - 4)) * 60

    def num_trading_days(self, symbol: str, start: date, end: date) -> int:
        if type(start) == str:
            start = date_parser(start)  # type: ignore
        if type(end) == str:
            end = date_parser(end)  # type: ignore

        return (
            (end - start).days + 1
            if self._is_crypto_symbol(symbol)
            else len(
                pd.date_range(
                    start,
                    end,
                    freq=pd.tseries.offsets.CustomBusinessDay(
                        holidays=self.get_trading_holidays()
                    ),
                )
            )
        )

    def get_max_data_points_per_load(self) -> int:
        # Alpaca suggests 10000 points
        return 10000

    def _is_crypto_symbol(self, symbol: str) -> bool:
        return symbol.lower() in {"btcusd", "ethusd"}

    def trading_days_slice(self, symbol: str, s: slice) -> slice:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        if self._is_crypto_symbol(symbol):
            return s

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
            if config.detailed_dl_debug_enabled:
                tlog(f"symbol={symbol}, timeframe={t}, range=({_start, _end})")

            data = (
                self.crypto_get_symbol_data(
                    symbol=symbol, start=_start, end=_end, timeframe=t
                )
                if self._is_crypto_symbol(symbol)
                else self.alpaca_rest_client.get_bars(
                    symbol=symbol,
                    timeframe=t,
                    start=_start,
                    end=_end,
                    limit=1000000,
                    adjustment="all",
                ).df
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
