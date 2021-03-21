import sys
import traceback
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Dict

import alpaca_trade_api as tradeapi
import pandas as pd
from dateutil.parser import parse as date_parser
from pytz import timezone

from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import TimeScale
from liualgotrader.data.data_base import DataAPI
from liualgotrader.data.data_factory import data_loader_factory

nyc = timezone("America/New_York")


class SymbolData:
    class _Column:
        def __init__(self, data_api: DataAPI, name: str, data: object):
            self.name = name
            self.data_api = data_api
            self.data = data

        def __repr__(self):
            return str(self.data.symbol_data[self.name])

        def __getitem__(self, key):
            try:
                if type(key) == slice:
                    if not key.start and not len(self.data.symbol_data):
                        raise ValueError(f"[:{key.stop}] is not a valid slice")
                    if not key.stop:
                        key = slice(key.start, -1)

                    if type(key.start) == str:
                        _key_start = nyc.localize(date_parser(key.start))
                        key = slice(_key_start, key.stop)
                    elif type(key.start) == int:
                        if self.data.scale == TimeScale.minute:
                            if len(self.data.symbol_data):
                                _key_start = self.data.symbol_data.index[
                                    -1
                                ] + timedelta(minutes=1 + key.start)
                            else:
                                _key_start = datetime.now(tz=nyc).replace(
                                    second=0, microsecond=0
                                ) + timedelta(minutes=1 + key.start)
                        elif self.data.scale == TimeScale.day:
                            _key_start = datetime.now(tz=nyc).replace(
                                second=0, microsecond=0
                            ) + timedelta(days=1 + key.start)
                        key = slice(_key_start, key.stop)
                    elif type(key.start) == date:
                        key = slice(
                            nyc.localize(
                                datetime.combine(
                                    key.start, datetime.min.time()
                                )
                            ),
                            key.stop,
                        )

                    if type(key.stop) == str:
                        _key_stop = nyc.localize(
                            date_parser(key.stop)
                        ) + timedelta(days=1)
                        key = slice(key.start, _key_stop)
                    elif type(key.stop) == int:
                        if self.data.scale == TimeScale.minute:
                            if len(self.data.symbol_data):
                                _key_end = self.data.symbol_data.index[
                                    -1
                                ] + timedelta(minutes=1 + key.stop)
                            else:
                                _key_end = datetime.now(tz=nyc).replace(
                                    second=0, microsecond=0
                                ) + timedelta(minutes=1 + key.stop)
                        elif self.data.scale == TimeScale.day:
                            _key_end = datetime.now(tz=nyc).replace(
                                second=0, microsecond=0
                            ) + timedelta(days=1 + key.stop)
                        key = slice(key.start, _key_end)
                    elif type(key.stop) == date:
                        key = slice(
                            key.start,
                            nyc.localize(
                                datetime.combine(key.stop, datetime.min.time())
                            )
                            + timedelta(days=1),
                        )

                    if (
                        not len(self.data.symbol_data)
                        or key.stop > self.data.symbol_data.index[-1]
                    ):
                        self.data.fetch_data_timestamp(key.stop)

                    if key.start <= self.data.symbol_data.index[0]:
                        self.data.fetch_data_range(
                            key.start, self.data.symbol_data.index[0]
                        )

                    start_index = self.data.symbol_data.index.get_loc(
                        key.start, method="ffill"
                    )

                    stop_index = self.data.symbol_data.index.get_loc(
                        key.stop, method="ffill"
                    )

                    return self.data.symbol_data.iloc[
                        start_index : stop_index + 1
                    ][self.name]
                else:
                    if type(key) == str:
                        key = nyc.localize(date_parser(key))
                    elif type(key) == int:
                        if self.data.scale == TimeScale.minute:
                            if not len(self.data.symbol_data):
                                key = datetime.now(tz=nyc).replace(
                                    second=0, microsecond=0
                                ) + timedelta(minutes=1 + key)
                            else:
                                key = self.data.symbol_data.index[
                                    -1
                                ] + timedelta(minutes=1 + key)
                        elif self.data.scale == TimeScale.day:
                            key = datetime.now(tz=nyc).replace(
                                second=0, microsecond=0
                            ) + timedelta(days=1 + key)
                    elif type(key) == date:
                        key = nyc.localize(
                            datetime.combine(key, datetime.min.time())
                        )

                    if (
                        not len(self.data.symbol_data)
                        or key > self.data.symbol_data.index[-1]
                    ):
                        self.data.fetch_data_timestamp(key)

                    if not len(self.data.symbol_data):
                        raise ValueError(
                            f"details for symbol {self.data.symbol} do not exist"
                        )

                    return self.data.symbol_data.iloc[
                        self.data.symbol_data.index.get_loc(
                            key, method="ffill"
                        )
                    ][self.name]

            except Exception:
                traceback.print_exc()
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
        self.symbol_data = pd.DataFrame()

    def __getattr__(self, attr) -> _Column:
        if attr[0:3] == "loc" or attr[0:4] == "iloc":
            return self.symbol_data.__getattr__(attr)
        elif attr not in self.columns:
            self.columns[attr] = self._Column(self.data_api, attr, self)
        return self.columns[attr]

    def __getitem__(self, key):
        try:
            if type(key) == slice:
                if not key.start:
                    raise ValueError(f"[:{key.stop}] is not a valid slice")
                if not key.stop:
                    key = slice(key.start, -1)

                if type(key.start) == str:
                    _key_start = nyc.localize(date_parser(key.start))
                    key = slice(_key_start, key.stop)
                elif type(key.start) == int:
                    if self.scale == TimeScale.minute:
                        if len(self.symbol_data):
                            _key_start = self.symbol_data.index[
                                -1
                            ] + timedelta(minutes=1 + key.start)
                        else:
                            _key_start = datetime.now(tz=nyc).replace(
                                second=0, microsecond=0
                            ) + timedelta(minutes=1 + key.start)
                    elif self.scale == TimeScale.day:
                        _key_start = datetime.now(tz=nyc).replace(
                            second=0, microsecond=0
                        ) + timedelta(days=1 + key.start)
                    key = slice(_key_start, key.stop)
                elif type(key.start) == date:
                    key = slice(
                        nyc.localize(
                            datetime.combine(key.start, datetime.min.time())
                        ),
                        key.stop,
                    )

                if type(key.stop) == str:
                    _key_stop = nyc.localize(
                        date_parser(key.stop)
                    ) + timedelta(days=1)
                    key = slice(key.start, _key_stop)
                elif type(key.stop) == int:
                    if self.scale == TimeScale.minute:
                        if len(self.symbol_data):
                            _key_end = self.symbol_data.index[-1] + timedelta(
                                minutes=1 + key.stop
                            )
                        else:
                            _key_end = datetime.now(tz=nyc).replace(
                                second=0, microsecond=0
                            ) + timedelta(minutes=1 + key.stop)
                    elif self.scale == TimeScale.day:
                        _key_end = datetime.now(tz=nyc).replace(
                            second=0, microsecond=0
                        ) + timedelta(days=1 + key.stop)
                    key = slice(key.start, _key_end)
                elif type(key.stop) == date:
                    key = slice(
                        key.start,
                        nyc.localize(
                            datetime.combine(key.stop, datetime.min.time())
                        )
                        + timedelta(days=1),
                    )

                if (
                    not len(self.symbol_data)
                    or key.stop > self.symbol_data.index[-1]
                ):
                    self.fetch_data_timestamp(key.stop)

                if (
                    not len(self.symbol_data)
                    or key.start <= self.symbol_data.index[0]
                ):
                    self.fetch_data_range(key.start, self.symbol_data.index[0])

                try:
                    start_index = self.symbol_data.index.get_loc(
                        key.start, method="ffill"
                    )
                except KeyError:
                    start_index = self.symbol_data.index.get_loc(
                        key.start, method="nearest"
                    )
                except pd.errors.InvalidIndexError:
                    print(key)
                    print(self.symbol_data)
                    raise

                try:
                    stop_index = self.symbol_data.index.get_loc(
                        key.stop, method="ffill"
                    )
                except KeyError:
                    stop_index = self.symbol_data.index.get_loc(
                        key.stop, method="nearest"
                    )

                return self.symbol_data.iloc[start_index : stop_index + 1]
            else:
                if type(key) == str:
                    key = nyc.localize(date_parser(key))
                if (
                    not len(self.symbol_data)
                    or key > self.symbol_data.index[-1]
                ):
                    self.fetch_data_timestamp(key)

                if type(key) == int:
                    return self.symbol_data.iloc[key]

                return self.symbol_data.iloc[
                    self.symbol_data.index.get_loc(key, method="ffill")
                ]
        except Exception:
            traceback.print_exc()
            raise

    def fetch_data_timestamp(self, timestamp: pd.Timestamp) -> None:
        if self.scale not in (TimeScale.minute, TimeScale.day):
            return

        if type(timestamp) == pd.Timestamp:
            _start = timestamp.to_pydatetime() - timedelta(
                days=6 if self.scale == TimeScale.minute else 500
            )
            _end = timestamp.to_pydatetime() + timedelta(days=1)
        elif type(timestamp) == int:
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
            _start = _end - timedelta(
                days=6 if self.scale == TimeScale.minute else 500
            )
        else:
            _start = timestamp - timedelta(
                days=6 if self.scale == TimeScale.minute else 500
            )
            _end = timestamp + timedelta(days=1)

        _df = self.data_api.get_symbol_data(
            self.symbol,
            start=_start.date() if type(_start) != date else _start,
            end=_end.date() if type(_end) != date else _end,
            scale=self.scale,
        )
        self.symbol_data = pd.concat(
            [self.symbol_data, _df]
        ).drop_duplicates()
        self.symbol_data = self.symbol_data.loc[
            ~self.symbol_data.index.duplicated(keep="first")
        ]

    def fetch_data_range(self, start: datetime, end: datetime) -> None:
        if self.scale not in (TimeScale.minute, TimeScale.day):
            return

        new_df = pd.DataFrame()
        while end >= start:
            if type(end) == pd.Timestamp:
                _start = (
                    end
                    - timedelta(
                        days=7 if self.scale == TimeScale.minute else 500
                    )
                ).date()
                _end = end.date()
            else:
                _start = end - timedelta(
                    days=7 if self.scale == TimeScale.minute else 500
                )
                _end = end

            _df = self.data_api.get_symbol_data(
                self.symbol,
                start=_start,
                end=_end,
                scale=self.scale,
            )
            new_df = pd.concat([_df, new_df]).drop_duplicates()

            end -= timedelta(
                days=7 if self.scale == TimeScale.minute else 500
            )

        # new_df = new_df[~new_df.index.duplicated(keep="first")]
        self.symbol_data = pd.concat(
            [new_df, self.symbol_data]
        ).drop_duplicates()
        self.symbol_data = self.symbol_data[
            ~self.symbol_data.index.duplicated(keep="first")
        ]


class DataLoader:
    def __init__(self, scale: TimeScale = TimeScale.minute):
        self.data_api = data_loader_factory()
        self.data: Dict[str, SymbolData] = {}
        if not self.data_api:
            raise AssertionError("Failed to create data loader")

        self.scale = scale

    def __getitem__(self, symbol: str) -> SymbolData:
        if not self.data_api:
            raise AssertionError("Must call a well constructed object")

        if symbol not in self.data:
            self.data[symbol] = SymbolData(self.data_api, symbol, self.scale)

        return self.data[symbol]
