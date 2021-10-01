# type: ignore
from datetime import date, datetime, timedelta
from typing import Dict, Tuple

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


class SymbolData:
    class _Column:
        def __init__(
            self,
            data_api: DataAPI,
            name: str,
            data: object,
        ):
            self.name = name
            self.data_api = data_api
            self.data = data

        def __repr__(self):
            return str(self.data.symbol_data[self.name])

        def _convert_offset_to_datetime(self, offset: int) -> datetime:
            if self.data.scale == TimeScale.minute:
                if len(self.data.symbol_data):
                    _rc = self.data.symbol_data.index[-1] + timedelta(
                        minutes=1 + offset
                    )
                else:
                    _rc = datetime.now(tz=nyc).replace(
                        second=0, microsecond=0
                    ) + timedelta(minutes=1 + offset)
            elif self.data.scale == TimeScale.day:
                _rc = datetime.now(tz=nyc).replace(
                    second=0, microsecond=0
                ) + timedelta(days=1 + offset)

            return _rc

        def _handle_slice_conversion(self, key: slice) -> slice:
            # handle slide start
            if type(key.start) == str:
                key = slice(nyc.localize(date_parser(key.start)), key.stop)
            elif type(key.start) == int:
                key = slice(
                    self._convert_offset_to_datetime(key.start), key.stop
                )
            elif type(key.start) == date:
                key = slice(
                    nyc.localize(
                        datetime.combine(key.start, datetime.min.time())
                    ),
                    key.stop,
                )

            # handle slice end
            if type(key.stop) == str:
                key = slice(
                    key.start,
                    nyc.localize(date_parser(key.stop)) + timedelta(days=1),
                )
            elif type(key.stop) == int:
                key = slice(
                    key.start, self._convert_offset_to_datetime(key.stop)
                )
            elif type(key.stop) == date:
                key = slice(
                    key.start,
                    nyc.localize(
                        datetime.combine(key.stop, datetime.min.time())
                    )
                    + timedelta(days=1),
                )
            return key

        def _get_index(self, index: datetime, method: str = "ffill") -> int:
            try:
                return self.data.symbol_data.index.get_loc(
                    index, method=method
                )
            except KeyError:
                self.data.fetch_data_timestamp(index)
                return self.data.symbol_data.index.get_loc(
                    index, method="nearest"
                )

        def _getitem_slice(self, key):
            if not key.start and not len(self.data.symbol_data):
                raise ValueError(f"[:{key.stop}] is not a valid slice")
            if not key.stop:
                key = slice(key.start, -1)

            # ensure key represents datetime
            key = self._handle_slice_conversion(key)

            # load data, if missing
            if (
                not len(self.data.symbol_data)
                or key.stop > self.data.symbol_data.index[-1]
            ):
                self.data.fetch_data_timestamp(key.stop)

            if key.start <= self.data.symbol_data.index[0]:
                self.data.fetch_data_range(
                    key.start, self.data.symbol_data.index[0]
                )

            # get start and end index
            start_index = self._get_index(key.start, method="bfill")
            stop_index = self._get_index(key.stop)

            # return data range
            return self.data.symbol_data.iloc[start_index : stop_index + 1][
                self.name
            ]

        def _getitem(self, key):
            if type(key) == str:
                key = nyc.localize(date_parser(key))
            elif type(key) == int:
                key = self._convert_offset_to_datetime(key)
            elif type(key) == date:
                key = nyc.localize(datetime.combine(key, datetime.min.time()))

            if (
                not len(self.data.symbol_data)
                or key > self.data.symbol_data.index[-1]
            ):
                self.data.fetch_data_timestamp(key)

            if not len(self.data.symbol_data):
                raise ValueError(
                    f"details for symbol {self.data.symbol} do not exist"
                )

            try:
                return self.data.symbol_data.iloc[
                    self.data.symbol_data.index.get_loc(key, method="ffill")
                ][self.name]

            except ValueError:
                tlog(
                    f"[EXCEPTION] ValueError {key},{repr(key)},{type(key)} {self.data.symbol_data.index[-760:]}"
                )
                raise
            except KeyError:
                self.data.fetch_data_timestamp(key)
                return self.data.symbol_data.index.get_loc(
                    key, method="nearest"
                )

        def __getitem__(self, key):
            try:
                if type(key) == slice:
                    return self._getitem_slice(key)
                return self._getitem(key)
            except Exception:
                if config.debug_enabled:
                    tlog_exception("__getitem__")
                raise

        def __getattr__(self, attr):
            return self.data.symbol_data[self.name].__getattr__(attr)

        def __call__(self):
            return self.data.symbol_data[self.name]

    def __init__(self, data_api: tradeapi, symbol: str, scale: TimeScale):
        self.data_api = data_api
        self.symbol = symbol
        self.scale = scale
        self.columns: Dict[str, self._Column] = {}  # type: ignore
        self.symbol_data = pd.DataFrame(
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

    #    def __setattr__(self, name, value):
    #        return self.symbol_data.__setattr__(name, value)

    def __getattr__(self, attr) -> _Column:
        if attr[0:3] == "loc" or attr[0:4] == "iloc" or attr[0:5] == "apply":
            return self.symbol_data.__getattr__(attr)
        elif attr not in self.columns:
            self.columns[attr] = self._Column(self.data_api, attr, self)
        return self.columns[attr]

    def _convert_offset_to_datetime(self, offset: int) -> datetime:
        if self.scale == TimeScale.minute:
            if len(self.symbol_data):
                _rc = self.symbol_data.index[-1] + timedelta(
                    minutes=1 + offset
                )
            else:
                _rc = datetime.now(tz=nyc).replace(
                    second=0, microsecond=0
                ) + timedelta(minutes=1 + offset)
        elif self.scale == TimeScale.day:
            _rc = datetime.now(tz=nyc).replace(
                second=0, microsecond=0
            ) + timedelta(days=1 + offset)

        return _rc

    def _handle_slice_conversion(self, key: slice) -> slice:
        # handle slide start
        if type(key.start) == str:
            key = slice(nyc.localize(date_parser(key.start)), key.stop)
        elif type(key.start) == int:
            key = slice(self._convert_offset_to_datetime(key.start), key.stop)
        elif type(key.start) == date:
            key = slice(
                nyc.localize(datetime.combine(key.start, datetime.min.time())),
                key.stop,
            )

        # handle slice end
        if type(key.stop) == str:
            key = slice(
                key.start,
                nyc.localize(date_parser(key.stop)) + timedelta(days=1),
            )
        elif type(key.stop) == int:
            key = slice(key.start, self._convert_offset_to_datetime(key.stop))
        elif type(key.stop) == date:
            key = slice(
                key.start,
                nyc.localize(datetime.combine(key.stop, datetime.min.time()))
                + timedelta(days=1),
            )
        return key

    def _get_index(self, index: datetime, method: str = "ffill") -> int:
        try:
            return self.symbol_data.index.get_loc(index, method=method)
        except ValueError:
            tlog(f"[EXCEPTION] ValueError {index},{self.symbol_data.index}")
            raise
        except KeyError:
            self.fetch_data_timestamp(index)
            return self.symbol_data.index.get_loc(index, method="nearest")

    def _getitem_slice(self, key):
        if not key.start:
            raise ValueError(f"[:{key.stop}] is not a valid slice")

        if not key.stop:
            key = slice(key.start, -1)

        # handle slice conversations
        key = self._handle_slice_conversion(key)

        # load data
        if not len(self.symbol_data) or key.stop > self.symbol_data.index[-1]:
            self.fetch_data_timestamp(key.stop)

        if not len(self.symbol_data) or key.start <= self.symbol_data.index[0]:
            self.fetch_data_range(key.start, self.symbol_data.index[0])

        # get index for start & end
        start_index = self._get_index(key.start, method="bfill")
        stop_index = self._get_index(key.stop)

        return self.symbol_data.iloc[start_index : stop_index + 1]

    def __getitem__(self, key):
        if type(key) == str and key in self.symbol_data.columns.tolist():
            return self.symbol_data[key]

        if type(key) == slice:
            return self._getitem_slice(key)

        if type(key) == str:
            key = nyc.localize(date_parser(key))
        elif type(key) == int:
            key = self._convert_offset_to_datetime(key)
        elif type(key) == date:
            key = nyc.localize(datetime.combine(key, datetime.min.time()))

        if not len(self.symbol_data) or key > self.symbol_data.index[-1]:
            self.fetch_data_timestamp(key)

        if type(key) == int:
            return self.symbol_data.iloc[key]

        return self.symbol_data.iloc[
            self.symbol_data.index.get_loc(key, method="ffill")
        ]

    def _convert_timestamp(
        self, timestamp: pd.Timestamp
    ) -> Tuple[datetime, datetime]:
        return (
            timestamp.to_pydatetime()
            - timedelta(days=6 if self.scale == TimeScale.minute else 100),
            timestamp.to_pydatetime() + timedelta(days=1),
        )

    def _convert_int(
        self, timestamp: pd.Timestamp
    ) -> Tuple[datetime, datetime]:
        if self.scale == TimeScale.minute:
            if not len(self.symbol_data):
                _end = datetime.now(tz=nyc).replace(
                    second=0, microsecond=0
                ) + timedelta(minutes=1 + timestamp)
            else:
                _end = self.symbol_data.index[-1] + timedelta(
                    minutes=1 + timestamp
                )
        elif self.scale == TimeScale.day:
            _end = datetime.now(tz=nyc).replace(
                second=0, microsecond=0
            ) + timedelta(days=1 + timestamp)

        return (
            _end
            - timedelta(days=6 if self.scale == TimeScale.minute else 100),
            _end,
        )

    def _fetch_data_range(self, start, end):
        _df = self.data_api.get_symbol_data(
            self.symbol,
            start=start.date() if type(start) != date else start,
            end=end.date() if type(end) != date else end,
            scale=self.scale,
        )

        self.symbol_data = pd.concat(
            [self.symbol_data, _df], sort=True
        ).drop_duplicates()

        self.symbol_data = self.symbol_data.loc[
            ~self.symbol_data.index.duplicated(keep="first")
        ]
        self.symbol_data = self.symbol_data.reindex(
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

    def fetch_data_timestamp(self, timestamp: pd.Timestamp) -> None:
        if type(timestamp) == pd.Timestamp:
            _start, _end = self._convert_timestamp(timestamp)

        elif type(timestamp) == int:
            _start, _end = self._convert_int(timestamp)
        else:
            _start = timestamp - timedelta(
                days=6 if self.scale == TimeScale.minute else 100
            )
            _end = timestamp + timedelta(days=1)

        self._fetch_data_range(_start, _end)

    def fetch_data_range(self, start: datetime, end: datetime) -> None:
        new_df = pd.DataFrame()
        while end >= start:
            if type(end) == pd.Timestamp:
                _start = (
                    end
                    - timedelta(
                        days=7 if self.scale == TimeScale.minute else 100
                    )
                ).date()
                _end = end.date()
            else:
                _start = end - timedelta(
                    days=7 if self.scale == TimeScale.minute else 100
                )
                _end = end

            _df = self.data_api.get_symbol_data(
                self.symbol,
                start=_start,
                end=_end,
                scale=self.scale,
            )

            new_df = pd.concat([_df, new_df], sort=True).drop_duplicates()

            end -= timedelta(days=7 if self.scale == TimeScale.minute else 100)

        self.symbol_data = pd.concat(
            [new_df, self.symbol_data], sort=True
        ).drop_duplicates()
        self.symbol_data = self.symbol_data[
            ~self.symbol_data.index.duplicated(keep="first")
        ]
        self.symbol_data = self.symbol_data.reindex(
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

    def __repr__(self):
        return str(self.symbol_data)


class DataLoader:
    def __init__(
        self,
        scale: TimeScale = TimeScale.minute,
        connector: DataConnectorType = config.data_connector,
    ):
        self.data_api = data_loader_factory(connector)
        self.data: Dict[str, SymbolData] = {}
        if not self.data_api:
            raise AssertionError("Failed to create data loader")

        self.scale = scale

    def exist(self, symbol: str) -> bool:
        return symbol in self.data

    def __getattr__(self, attr):
        return self.__getitem__(attr)

    def __getitem__(self, symbol: str) -> SymbolData:
        if not self.data_api:
            raise AssertionError("Must call a well constructed object")

        if symbol not in self.data:
            self.data[symbol] = SymbolData(self.data_api, symbol, self.scale)

        return self.data[symbol]
