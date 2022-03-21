# type: ignore
import concurrent.futures
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import alpaca_trade_api as tradeapi
import nest_asyncio
import pandas as pd
from dateutil.parser import parse as date_parser
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog, tlog_exception
from liualgotrader.common.types import DataConnectorType, TimeScale
from liualgotrader.data.data_base import DataAPI
from liualgotrader.data.data_factory import data_loader_factory

nest_asyncio.apply()

nyc = timezone("America/New_York")

m_and_a_data = pd.read_csv(
    "https://raw.githubusercontent.com/amor71/LiuAlgoTrader/master/database/market_m_a_data.csv"
).set_index("date")


def _calc_data_to_fetch(s: slice, index: pd.Index) -> List[slice]:
    if index.empty:
        return [s]

    slices = []

    if s.start.date() < index[0].date():
        slices.append(slice(s.start, index[0]))

    if s.stop.date() > index[-1].date():
        slices.append(slice(index[-1], s.stop))

    return slices


def convert_offset_to_datetime(
    data_api: DataAPI,
    symbol: str,
    index: pd.Index,
    scale: TimeScale,
    offset: int,
    start: Optional[datetime] = None,
) -> datetime:
    try:
        return index[offset]
    except IndexError:
        last_trading_time = start or data_api.get_last_trading(symbol)
        if scale == TimeScale.minute:
            return last_trading_time.replace(
                second=0, microsecond=0
            ) + timedelta(minutes=1 + offset)

        return data_api.get_trading_day(
            symbol, last_trading_time.date(), 1 + offset
        )


def handle_slice_conversion(
    data_api: DataAPI,
    symbol: str,
    key: slice,
    scale: TimeScale,
    index: pd.Index,
) -> slice:
    # handle slice end
    if type(key.stop) == str:
        key = slice(
            key.start,
            nyc.localize(date_parser(key.stop)),
        )
    elif type(key.stop) == int:
        key = slice(
            key.start,
            convert_offset_to_datetime(
                data_api, symbol, index, scale, key.stop
            ),
        )
    elif type(key.stop) == date:
        key = slice(
            key.start,
            nyc.localize(
                datetime.combine(
                    key.stop + timedelta(days=1), datetime.min.time()
                )
            ),
        )
    elif type(key.stop) == datetime and key.stop.tzinfo is None:
        key = slice(key.start, nyc.localize(key.stop))

    # handle slide start
    if type(key.start) == str:
        key = slice(nyc.localize(date_parser(key.start)), key.stop)
    elif type(key.start) == int:
        key = slice(
            convert_offset_to_datetime(
                data_api, symbol, index, scale, key.start, key.stop
            ),
            key.stop,
        )
    elif type(key.start) == date:
        key = slice(
            nyc.localize(datetime.combine(key.start, datetime.min.time())),
            key.stop,
        )
    elif type(key.start) == datetime and key.start.tzinfo is None:
        key = slice(nyc.localize(key.start), key.stop)

    return key


def load_item_by_offset(
    data_api: DataAPI,
    symbol_data: pd.DataFrame,
    symbol: str,
    scale: TimeScale,
    offset: int,
    concurrency: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    i = convert_offset_to_datetime(
        data_api=data_api,
        symbol=symbol,
        index=symbol_data.index,
        scale=scale,
        offset=offset,
    )
    symbol_data = fetch_data_datetime(
        data_api=data_api,
        symbol_data=symbol_data,
        symbol=symbol,
        scale=scale,
        d=i,
        concurrency=concurrency,
    )
    # index = symbol_data.index.get_indexer([i], method="nearest")[0]
    return (
        symbol_data,
        symbol_data.iloc[offset],  # index
    )


def get_item_by_offset(
    data_api: DataAPI,
    symbol_data: pd.DataFrame,
    symbol: str,
    scale: TimeScale,
    offset: int,
    concurrency: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    try:
        return symbol_data, symbol_data.iloc[len(symbol_data.index) + offset]
    except IndexError:
        return load_item_by_offset(
            data_api, symbol_data, symbol, scale, offset, concurrency
        )


def _data_fetch_executor(
    data_api: DataAPI,
    symbol: str,
    scale: TimeScale,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:

    df = data_api.get_symbol_data(
        symbol,
        start=(start.date() if isinstance(start, datetime) else start),
        end=(end.date() if isinstance(end, datetime) else end)
        + timedelta(days=1),
        scale=scale,
    )

    return df.reindex(
        columns=[
            "open",
            "high",
            "low",
            "close",
            "volume",
            "vwap",
            "average",
            "count",
        ]
    ).sort_index()


def _concurrent_fetch_data(
    data_api: DataAPI,
    symbol_data: pd.DataFrame,
    symbol: str,
    scale: TimeScale,
    start: datetime,
    end: datetime,
):
    ranges = data_api.data_concurrency_ranges(
        symbol=symbol, start=start, end=end, scale=scale
    )
    if not len(ranges):
        raise ValueError(f"can't load empty range list {ranges}")

    ranges = list(zip(ranges, ranges[1:]))
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(
                _data_fetch_executor,
                data_api,
                symbol,
                scale,
                range[0],
                range[1],
            ): range
            for range in ranges
        }
        for future in concurrent.futures.as_completed(futures):
            response = future.result()
            symbol_data = pd.concat([symbol_data, response])
            symbol_data = symbol_data[
                ~symbol_data.index.duplicated(keep="first")
            ].sort_index()

    return symbol_data.reindex(
        columns=[
            "open",
            "high",
            "low",
            "close",
            "volume",
            "vwap",
            "average",
            "count",
        ]
    ).sort_index()


def _legacy_fetch_data_range(
    data_api: DataAPI,
    symbol_data: pd.DataFrame,
    symbol: str,
    scale: TimeScale,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:

    adjusted_symbol = symbol
    m_and_a_data.index = m_and_a_data.index.astype("datetime64[ns]", copy=True)
    while True:
        adjusted_data = m_and_a_data.loc[
            (
                end.replace(
                    hour=0, minute=0, second=0, microsecond=0, tzinfo=None
                )
                <= m_and_a_data.index
            )
            & (m_and_a_data.to_symbol == adjusted_symbol)
        ]
        if not adjusted_data.empty:
            adjusted_symbol = adjusted_data.from_symbol.item()
        else:
            break

    if adjusted_symbol != symbol:
        adjusted_df = data_api.get_symbol_data(
            adjusted_symbol,
            start=(start.date() if isinstance(start, datetime) else start),
            end=(end.date() if isinstance(end, datetime) else end)
            + timedelta(days=1),
            scale=scale,
        )
    else:
        adjusted_df = pd.DataFrame()

    new_df = data_api.get_symbol_data(
        symbol,
        start=(start.date() if isinstance(start, datetime) else start),
        end=(end.date() if isinstance(end, datetime) else end)
        + timedelta(days=1),
        scale=scale,
    )
    symbol_data = pd.concat([adjusted_df, new_df, symbol_data], sort=True)
    symbol_data = symbol_data[~symbol_data.index.duplicated(keep="first")]
    return symbol_data.reindex(
        columns=[
            "open",
            "high",
            "low",
            "close",
            "volume",
            "vwap",
            "average",
            "count",
        ]
    ).sort_index()


def fetch_data_range(
    data_api: DataAPI,
    symbol_data: pd.DataFrame,
    symbol: str,
    scale: TimeScale,
    start: datetime,
    end: datetime,
    concurrency: int,
) -> pd.DataFrame:
    if concurrency:
        return _concurrent_fetch_data(
            data_api=data_api,
            symbol_data=symbol_data,
            symbol=symbol,
            scale=scale,
            start=start,
            end=end,
        )
    else:
        return _legacy_fetch_data_range(
            data_api=data_api,
            symbol_data=symbol_data,
            symbol=symbol,
            scale=scale,
            start=start,
            end=end,
        )


def fetch_data_datetime(
    data_api: DataAPI,
    symbol_data: pd.DataFrame,
    symbol: str,
    scale: TimeScale,
    d: datetime,
    concurrency: int,
) -> pd.DataFrame:
    if not symbol_data.empty and d < symbol_data.index.min():
        start = d
        end = symbol_data.index.min()
    elif not symbol_data.empty and d > symbol_data.index.max():
        start = symbol_data.index.max()
        end = d + (
            timedelta(days=1)
            if scale == TimeScale.day
            else timedelta(minutes=1)
        )
    else:
        start = d
        end = d + (
            timedelta(days=1)
            if scale == TimeScale.day
            else timedelta(minutes=1)
        )

    return fetch_data_range(
        data_api=data_api,
        symbol_data=symbol_data,
        symbol=symbol,
        scale=scale,
        start=start,
        end=end,
        concurrency=concurrency,
    )


def getitem_slice(
    data_api: DataAPI,
    symbol: str,
    symbol_data: pd.DataFrame,
    scale: TimeScale,
    key: slice,
    concurrency: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    key = slice(key.start or 0, key.stop or -1)

    # ensure key represents datetime
    converted_key = handle_slice_conversion(
        data_api, symbol, key, scale, symbol_data.index
    )

    # load data if needed
    for s in _calc_data_to_fetch(converted_key, symbol_data.index):
        symbol_data = fetch_data_range(
            data_api=data_api,
            symbol_data=symbol_data,
            symbol=symbol,
            scale=scale,
            start=s.start,
            end=s.stop,
            concurrency=concurrency,
        )
    # return data range
    if not isinstance(key.start, int):
        key_start_index = symbol_data.index.get_indexer(
            [converted_key.start], method="nearest"
        )[0]
    elif key.start < 0:
        key_start_index = len(symbol_data.index) + key.start
    else:
        key_start_index = key.start

    if not isinstance(key.stop, int):
        key_end_index = symbol_data.index.get_indexer(
            [converted_key.stop], method="nearest"
        )[0]
    elif key.stop < 0:
        key_end_index = len(symbol_data.index) + key.stop
    else:
        key_end_index = key.stop

    return (
        symbol_data,
        symbol_data.iloc[key_start_index : key_end_index + 1],
    )


def getitem(
    data_api: DataAPI,
    symbol_data: pd.DataFrame,
    symbol: str,
    scale: TimeScale,
    key,
    concurrency,
):
    if type(key) == str:
        key = nyc.localize(date_parser(key))
    elif type(key) == int:
        symbol_data, rc = get_item_by_offset(
            data_api=data_api,
            symbol_data=symbol_data,
            symbol=symbol,
            scale=scale,
            offset=key,
            concurrency=concurrency,
        )
        return symbol_data, rc

    elif type(key) == date:
        key = nyc.localize(datetime.combine(key, datetime.min.time()))
    elif type(key) == datetime and key.tzinfo is None:
        key = nyc.localize(key)

    for s in _calc_data_to_fetch(
        slice(key, key + timedelta(days=1)), symbol_data.index
    ):
        symbol_data = fetch_data_range(
            data_api=data_api,
            symbol_data=symbol_data,
            symbol=symbol,
            scale=scale,
            start=s.start,
            end=s.stop,
            concurrency=concurrency,
        )

    if symbol_data.empty:
        raise ValueError(f"details for symbol {symbol} do not exist")

    index = symbol_data.index.get_indexer([key], method="ffill")[0]
    return symbol_data, symbol_data.iloc[index]


class SymbolData:
    class _Column:
        def __init__(
            self,
            data_api: DataAPI,
            name: str,
            data: object,
            scale: TimeScale,
            concurrency: int,
        ):
            self.name = name
            self.data_api = data_api
            self.data = data
            self.scale = scale
            self.concurrency = concurrency

        def __repr__(self):
            return str(self.data.symbol_data[self.name])

        def _get_index(self, index: datetime, method: str = "ffill") -> int:
            try:
                return self.data.symbol_data.index.get_loc(
                    index, method=method
                )
            except KeyError:
                self.data.symbol_data = fetch_data_datetime(
                    data_api=self.data_api,
                    symbol_data=self.data.symbol_data,
                    symbol=self.data.symbol,
                    scale=self.scale,
                    d=index,
                    concurrency=self.concurrency,
                )
                return self.data.symbol_data.index.get_loc(
                    index, method="nearest"
                )

        def __getitem__(self, key):
            try:
                if type(key) == slice:
                    self.data.symbol_data, rc = getitem_slice(
                        data_api=self.data_api,
                        symbol=self.data.symbol,
                        symbol_data=self.data.symbol_data,
                        scale=self.scale,
                        key=key,
                        concurrency=self.concurrency,
                    )
                    return rc[self.name]

                self.data.symbol_data, rc = getitem(
                    data_api=self.data_api,
                    symbol=self.data.symbol,
                    symbol_data=self.data.symbol_data,
                    scale=self.scale,
                    key=key,
                    concurrency=self.concurrency,
                )
                return rc[self.name]
            except Exception:
                if config.debug_enabled:
                    tlog_exception("__getitem__")
                raise

        def __getattr__(self, attr):
            return self.data.symbol_data[self.name].__getattr__(attr)

        def __call__(self):
            return self.data.symbol_data[self.name]

    def __init__(
        self,
        data_api: tradeapi,
        symbol: str,
        scale: TimeScale,
        concurrency: int,
        prefetched_data: Optional[pd.DataFrame] = None,
    ):
        self.data_api = data_api
        self.symbol = symbol
        self.scale = scale
        self.concurrency = concurrency
        self.columns: Dict[str, self._Column] = {}  # type: ignore

        self.symbol_data = (
            prefetched_data
            if prefetched_data is not None
            else pd.DataFrame(
                columns=[
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "vwap",
                    "average",
                    "count",
                ]
            )
        )

    #    def __setattr__(self, name, value):
    #        return self.symbol_data.__setattr__(name, value)

    def __getattr__(self, attr) -> _Column:
        if attr[:3] == "loc" or attr[:4] == "iloc" or attr[:5] == "apply":
            return self.symbol_data.__getattr__(attr)
        elif attr not in self.columns:
            self.columns[attr] = self._Column(
                self.data_api, attr, self, self.scale, self.concurrency
            )
        return self.columns[attr]

    def _get_index(self, index: datetime, method: str = "ffill") -> int:
        try:
            return self.symbol_data.index.get_loc(index, method=method)
        except ValueError:
            tlog(f"[EXCEPTION] ValueError {index},{self.symbol_data.index}")
            raise
        except KeyError:
            self.symbol_data = fetch_data_datetime(
                data_api=self.data_api,
                symbol_data=self.symbol_data,
                symbol=self.symbol,
                scale=self.scale,
                d=index,
                concurrency=self.concurrency,
            )
            return self.data.symbol_data.index.get_loc(index, method="nearest")

    def __getitem__(self, key):
        try:
            if type(key) == slice:
                self.symbol_data, rc = getitem_slice(
                    data_api=self.data_api,
                    symbol=self.symbol,
                    symbol_data=self.symbol_data,
                    scale=self.scale,
                    key=key,
                    concurrency=self.concurrency,
                )
                return rc

            self.symbol_data, rc = getitem(
                data_api=self.data_api,
                symbol=self.symbol,
                symbol_data=self.symbol_data,
                scale=self.scale,
                key=key,
                concurrency=self.concurrency,
            )
            return rc
        except Exception:
            if config.debug_enabled:
                tlog_exception("__getitem__")
            raise

    def __repr__(self):
        return str(self.symbol_data)


class DataLoader:
    def __init__(
        self,
        scale: TimeScale = TimeScale.minute,
        connector: DataConnectorType = config.data_connector,
        concurrency: Optional[int] = 0,
    ):
        self.data_api = data_loader_factory(connector)
        self.data: Dict[str, SymbolData] = {}
        self.scale = scale
        self.concurrency = concurrency
        if not self.data_api:
            raise AssertionError("Failed to create data loader")

    def keys(self) -> List[str]:
        return list(self.data.keys())

    def pre_fetch(self, symbols: List[str], start: date, end: date):
        data = self.data_api.get_symbols_data(
            symbols=symbols, start=start, end=end, scale=self.scale
        )
        for symbol, df in data.items():
            self.data[symbol] = SymbolData(
                self.data_api, symbol, self.scale, self.concurrency, df
            )

    def exist(self, symbol: str) -> bool:
        return symbol in self.data

    def __len__(self) -> int:
        return len(self.data.keys())

    def __getattr__(self, attr):
        return self.__getitem__(attr)

    def __getitem__(self, symbol: str) -> SymbolData:
        if not self.data_api:
            raise AssertionError("Must call a well constructed object")

        if symbol not in self.data:
            self.data[symbol] = SymbolData(
                self.data_api, symbol, self.scale, self.concurrency
            )

        return self.data[symbol]
