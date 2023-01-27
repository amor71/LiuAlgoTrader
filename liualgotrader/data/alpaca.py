import asyncio
import concurrent.futures
import queue
import time
import traceback
from datetime import date, datetime, timedelta
from random import randint
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd
import pandas_market_calendars
import pytz
import requests
from alpaca.common.exceptions import APIError
from alpaca.data import (CryptoBarsRequest, CryptoHistoricalDataClient,
                         StockBarsRequest, StockHistoricalDataClient,
                         StockSnapshotRequest)
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.live import CryptoDataStream, StockDataStream
from alpaca.data.models import Bar, Trade
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.models import Calendar
from alpaca.trading.requests import GetCalendarRequest
from dateutil.parser import parse as date_parser

from liualgotrader.common import config
from liualgotrader.common.list_utils import chunks
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import QueueMapper, TimeScale, WSEventType
from liualgotrader.data.data_base import DataAPI
from liualgotrader.data.streaming_base import StreamingAPI

NY = "America/New_York"
nytz = pytz.timezone(NY)


def _is_crypto_symbol(symbol: str) -> bool:
    return symbol.lower() in {"eth/usd", "btc/usd"}


class AlpacaData(DataAPI):
    def __init__(self) -> None:

        self._ready = False
        self.alpaca_stock_data = StockHistoricalDataClient(
            api_key=config.alpaca_api_key, secret_key=config.alpaca_api_secret
        )
        self.alpaca_crypto_data = CryptoHistoricalDataClient(
            api_key=config.alpaca_api_key, secret_key=config.alpaca_api_secret
        )
        self.trading_client = TradingClient(
            api_key=config.alpaca_api_key,
            secret_key=config.alpaca_api_secret,
            paper=not config.alpaca_live_trading,
        )
        assert (
            self.alpaca_stock_data
        ), "Failed to authenticate Alpaca Stock data"
        assert (
            self.alpaca_crypto_data
        ), "Failed to authenticate Alpaca Crypto data"
        assert self.trading_client, "Failed to authenticate Alpaca Trading"

        # for requesting market snapshots by chunk of symbols
        self.symbol_chunk_size = 1000
        self.datetime_cache: Dict[datetime, datetime] = {}

        self._ready = True

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def get_market_snapshot(
        self, symbols: List[str], filter_func: Optional[Callable] = None
    ) -> List[Dict]:
        # parse market snapshots per chunk of symbols
        return await self._get_symbols_snapshot(symbols, filter_func)

    async def _get_symbols_snapshot(
        self, symbols: List[str], filter_func: Optional[Callable]
    ) -> List[Dict]:
        def _parse_ticker_snapshot(
            _ticker: str, _ticket_snapshot: Dict
        ) -> Dict:
            if not _ticket_snapshot:
                return {"ticker": _ticker}

            _ticket_snapshot["ticker"] = _ticker
            return _ticket_snapshot

        def _parse_snapshot_and_filter(_symbols: List[str]) -> List[Dict]:
            self.alpaca_stock_data._use_raw_data = True
            snapshots = self.alpaca_stock_data.get_stock_snapshot(
                StockSnapshotRequest(symbol_or_symbols=_symbols)
            )
            # self.alpaca_stock_data._use_raw_data = False
            processed_tickers_snapshot = map(
                lambda key_and_val: _parse_ticker_snapshot(*key_and_val),
                snapshots.items(),
            )
            return list(
                filter(
                    lambda snapshot: (  # type: ignore
                        (snapshot is not None) and (filter_func(snapshot))
                    ),
                    list(processed_tickers_snapshot),  # type : ignore
                )
                if filter_func is not None
                else processed_tickers_snapshot
            )

        # request snapshots per chunk of tickers by concurrency
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
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

    def get_last_trading(self, symbol: str) -> datetime:
        if _is_crypto_symbol(symbol):
            return datetime.now(tz=nytz)

        try:
            snapshot_data = self.alpaca_stock_data.get_stock_snapshot(
                StockSnapshotRequest(symbol_or_symbols=symbol)
            )
        except APIError as e:
            raise ValueError(
                f"get_last_trading() failed with APIError {e}"
            ) from None

        if min_bar := snapshot_data[symbol].latest_trade:
            return min_bar.timestamp.astimezone(tz=nytz)
        else:
            raise ValueError(f"Can't get snapshot for {symbol}")

    def get_trading_holidays(self) -> List[str]:
        nyse = pandas_market_calendars.get_calendar("NYSE")
        return nyse.holidays().holidays

    def get_trading_day(
        self, symbol: str, now: datetime, offset: int
    ) -> datetime:
        if _is_crypto_symbol(symbol):
            cbd_offset = timedelta(days=offset)
        else:
            cbd_offset = pd.tseries.offsets.CustomBusinessDay(
                n=offset - 1, holidays=self.get_trading_holidays()
            )
        return (
            nytz.localize(now + cbd_offset)
            if now.tzinfo is None
            else now + cbd_offset
        )

    def num_trading_minutes(self, symbol: str, start: date, end: date) -> int:
        return (24 if _is_crypto_symbol(symbol) else (20 - 4)) * 60

    def num_trading_days(self, symbol: str, start: date, end: date) -> int:
        if type(start) == str:
            start = date_parser(start)  # type: ignore
        if type(end) == str:
            end = date_parser(end)  # type: ignore

        return (
            (end - start).days + 1
            if _is_crypto_symbol(symbol)
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

    def trading_days_slice(self, symbol: str, s: slice) -> slice:
        if _is_crypto_symbol(symbol):
            return s

        if s.start in self.datetime_cache and s.stop in self.datetime_cache:
            return slice(
                self.datetime_cache[s.start], self.datetime_cache[s.stop]
            )

        trading_days: List[Calendar] = self.trading_client.get_calendar(  # type: ignore
            filters=GetCalendarRequest(start=s.start.date(), end=s.stop.date())
        )
        new_slice = slice(
            nytz.localize(trading_days[0].open),
            nytz.localize(trading_days[-1].open),
        )

        self.datetime_cache[s.start] = new_slice.start
        self.datetime_cache[s.stop] = new_slice.stop

        return new_slice

    def crypto_get_symbol_data(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: TimeFrame,
    ) -> pd.DataFrame:
        start = start.astimezone(tz=pytz.utc)
        end = end.astimezone(tz=pytz.utc)

        data = self.alpaca_crypto_data.get_crypto_bars(  # type:ignore
            CryptoBarsRequest(
                symbol_or_symbols=symbol,
                start=start,
                end=end,
                timeframe=timeframe,
            )
        ).df

        data = data.reset_index(level=0, drop=True)
        data = data.tz_convert("America/New_York")
        return self._extracted_from_get_symbols_data_14(data)

    def get_symbols_data(
        self,
        symbols: List[str],
        start: datetime,
        end: datetime,
        scale: TimeScale = TimeScale.minute,
    ) -> Dict[str, pd.DataFrame]:
        assert isinstance(symbols, list), f"{symbols} must be a list"

        start = start.astimezone(tz=pytz.utc)
        end = end.astimezone(tz=pytz.utc)

        t: TimeFrame = (
            TimeFrame(1, TimeFrameUnit.Minute)
            if scale == TimeScale.minute
            else TimeFrame(1, TimeFrameUnit.Day)
        )

        data = self.alpaca_stock_data.get_stock_bars(  # type:ignore
            StockBarsRequest(
                start=start,
                end=end,
                timeframe=t,
                symbol_or_symbols=symbols,
                adjustment=Adjustment.ALL,
            )
        ).df

        data = data.tz_convert("America/New_York", level=1)
        return self._extracted_from_get_symbols_data_14(data)

    # TODO Rename this here and in `crypto_get_symbol_data` and `get_symbols_data`
    def _extracted_from_get_symbols_data_14(self, data):
        data.rename(columns={"vwap": "average"}, inplace=True)
        data.rename(columns={"trade_count": "count"}, inplace=True)
        data["vwap"] = np.NaN
        return data

    def get_symbol_data(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        scale: TimeScale = TimeScale.minute,
    ) -> pd.DataFrame:
        t: TimeFrame = (
            TimeFrame(1, TimeFrameUnit.Minute)
            if scale == TimeScale.minute
            else TimeFrame(1, TimeFrameUnit.Day)
        )
        if scale == TimeScale.day and start.date() == end.date():
            start -= timedelta(days=1)
            end += timedelta(days=1)

        if _is_crypto_symbol(symbol):
            return self.crypto_get_symbol_data(
                symbol=symbol, start=start, end=end, timeframe=t
            )

        start = start.astimezone(tz=pytz.utc)
        end = end.astimezone(tz=pytz.utc)

        if config.detailed_dl_debug_enabled:
            tlog(f"symbol={symbol}, timeframe={t}, range=({start, end})")

        try:
            data = self.alpaca_stock_data.get_stock_bars(  # type:ignore
                StockBarsRequest(
                    start=start,
                    end=end,
                    timeframe=t,
                    symbol_or_symbols=symbol,
                    adjustment=Adjustment.ALL,
                )
            ).df
        except requests.exceptions.HTTPError as e:
            tlog(f"received HTTPError: {e}")
            if e.response.status_code in (500, 502, 504, 429):
                tlog("retrying")
                time.sleep(10)
                return self.get_symbol_data(symbol, start, end, scale)
            else:
                raise ValueError(
                    f"[EXCEPTION] {e} for {symbol} could not obtain data for {start} to {end} w {scale.name}"
                )
        else:
            if data.empty:
                raise ValueError(
                    f"[ERROR] {symbol} has no data for {start} to {end} w {scale.name}"
                )

        data = data.reset_index(level=0, drop=True)
        data = data.tz_convert("America/New_York")
        return self._extracted_from_get_symbols_data_14(data)


class AlpacaStream(StreamingAPI):
    def __init__(self, queues: QueueMapper):
        self.stock_data_stream = StockDataStream(
            api_key=config.alpaca_api_key,
            secret_key=config.alpaca_api_secret,
            feed=DataFeed.SIP
            if config.alpaca_data_feed.lower() == "sip"
            else DataFeed.IEX,
        )
        self.crypto_data_stream = CryptoDataStream(
            api_key=config.alpaca_api_key,
            secret_key=config.alpaca_api_secret,
        )
        assert (
            self.stock_data_stream
        ), "Failed to authenticate Alpaca Stock Stream client, check credentials and feed"
        assert (
            self.crypto_data_stream
        ), "Failed to authenticate Alpaca Crypto Stream client, check credentials and feed"

        self.stock_task: Optional[asyncio.Task] = None
        self.crypto_task: Optional[asyncio.Task] = None
        super().__init__(queues)

    async def run(self) -> None:
        if not self.queues:
            raise AssertionError(
                "can't call `AlpacaStream.run()` without queues"
            )

        if not self.stock_task:
            self.stock_task = asyncio.create_task(
                self.stock_data_stream._run_forever()
            )
        if not self.crypto_task:
            self.crypto_task = asyncio.create_task(
                self.crypto_data_stream._run_forever()
            )

    @classmethod
    async def bar_handler(cls, bar: Bar):
        print("bar_handler", Bar)
        try:
            event = {
                "symbol": bar.symbol,
                "open": bar.open,
                "close": bar.close,
                "high": bar.high,
                "low": bar.low,
                "timestamp": pd.to_datetime(
                    bar.timestamp, utc=True
                ).astimezone(nytz),
                "volume": bar.volume,
                "count": bar.trade_count,
                "vwap": np.nan,
                "average": bar.vwap,
                "totalvolume": None,
                "EV": "AM",
            }
            cls.get_instance().queues[bar.symbol].put(event, timeout=1)
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
    async def trades_handler(cls, trade: Trade):
        print("trades_handler", type(trade), trade)
        try:
            ts = pd.to_datetime(trade.timestamp)
            if (time_diff := (datetime.now(tz=nytz) - ts)) > timedelta(
                seconds=10
            ) and randint(  # nosec
                1, 100
            ) == 1:  # nosec
                tlog(
                    f"Received trade for {trade.symbol} too out of sync w {time_diff}"
                )

            event = {
                "symbol": trade.symbol,
                "price": trade.price,
                "open": trade.price,
                "close": trade.price,
                "high": trade.price,
                "low": trade.price,
                "timestamp": ts,
                "volume": trade.size,
                "exchange": trade.exchange,
                "conditions": trade.conditions,
                "tape": trade.tape,
                "average": np.nan,
                "count": 1,
                "vwap": np.nan,
                "EV": "T",
            }

            cls.get_instance().queues[trade.symbol].put(event, block=False)

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
        pass

    async def subscribe(
        self, symbols: List[str], events: List[WSEventType]
    ) -> bool:
        tlog(f"Starting subscription for {len(symbols)} symbols")
        upper_symbols = [symbol.upper() for symbol in symbols]
        for syms in chunks(upper_symbols, 1000):
            tlog(f"\tsubscribe {len(syms)}/{len(upper_symbols)}")

            crypto_symbols = list(filter(_is_crypto_symbol, syms))
            equity_symbols = [x for x in syms if x not in crypto_symbols]

            for event in events:
                if event == WSEventType.MIN_AGG:
                    # self.alpaca_ws_client._data_ws._running = False

                    if crypto_symbols:
                        self.crypto_data_stream.subscribe_bars(
                            AlpacaStream.bar_handler,
                            *crypto_symbols,
                        )
                    if equity_symbols:
                        self.stock_data_stream.subscribe_bars(
                            AlpacaStream.bar_handler,
                            *equity_symbols,
                        )
                elif event == WSEventType.TRADE:
                    if crypto_symbols:
                        self.crypto_data_stream.subscribe_trades(
                            AlpacaStream.trades_handler, *crypto_symbols
                        )
                    if equity_symbols:
                        self.stock_data_stream.subscribe_trades(
                            AlpacaStream.trades_handler, *equity_symbols
                        )
                elif event == WSEventType.QUOTE:
                    if crypto_symbols:
                        self.crypto_data_stream.subscribe_quotes(
                            AlpacaStream.quotes_handler, *crypto_symbols
                        )
                    if equity_symbols:
                        self.stock_data_stream.subscribe_quotes(
                            AlpacaStream.quotes_handler, *equity_symbols
                        )

            await asyncio.sleep(1)

        tlog(f"Completed subscription for {len(symbols)} symbols")
        return True

    async def close(self) -> None:
        tlog("Closing AlpacaStream")
        assert (
            self.stock_task and self.crypto_task
        ), "close() should not be called w/o a running task"

        # self.alpaca_ws_client.stop()
        await self.stock_data_stream.stop_ws()
        await self.crypto_data_stream.stop_ws()

        while not self.stock_task.done() and not self.crypto_task.done():
            await asyncio.sleep(1.0)

        tlog("Task Done. Closed AlpacaStream")
