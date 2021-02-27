import sys
import traceback
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict

import alpaca_trade_api as tradeapi
import pandas as pd

from liualgotrader.common.market_data import get_symbol_data


class TimeScale(Enum):
    DAILY = 24 * 60 * 60
    MINUTE = 60


class SymbolData:
    symbol_data = pd.DataFrame()

    class _Column:
        def __init__(self, data_api: tradeapi, name: str, data: object):
            self.name = name
            self.data_api = data_api
            self.data = data

        def __getitem__(self, key):
            try:
                if type(key) == slice:
                    if (
                        not len(self.data.symbol_data)
                        or key.stop > self.data.symbol_data.index[-1]
                    ):
                        self.data.fetch_data_timestamp(key.stop)
                    if type(key.start) == int:
                        start_index = (
                            key.start
                            if key.start > 0
                            else len(self.data.symbol_data.index) + key.start
                        )
                    else:
                        if key.start <= self.data.symbol_data.index[0]:
                            self.data.fetch_data_range(
                                key.start, self.data.symbol_data.index[0]
                            )

                        start_index = self.data.symbol_data.index.get_loc(
                            key.start, method="ffill"
                        )

                    stop_index = (
                        (
                            key.stop
                            if key.stop > 0
                            else len(self.data.symbol_data.index) + key.stop
                        )
                        if type(key.stop) == int
                        else self.data.symbol_data.index.get_loc(
                            key.stop, method="nearest"
                        )
                    )
                    return self.data.symbol_data.iloc[
                        start_index : stop_index + 1
                    ][self.name]
                else:
                    if (
                        not len(self.data.symbol_data)
                        or key > self.data.symbol_data.index[-1]
                    ):
                        self.data.fetch_data_timestamp(key)

                    return self.data.symbol_data.iloc[
                        self.data.symbol_data.index.get_loc(
                            key, method="ffill"
                        )
                    ][self.name]
            except Exception as e:
                traceback.print_exc()
            #    if type(key) == pd.Timestamp:
            #        self.data.fetch_data_timestamp(key)
            #        return self.__getitem__(key)

        def __getattr__(self, attr):
            return self.data.symbol_data[self.name].__getattr__(attr)

        def __call__(self):
            return self.data.symbol_data[self.name]

    def __init__(self, data_api: tradeapi, symbol: str, scale: TimeScale):
        self.data_api = data_api
        self.symbol = symbol
        self.scale = scale
        self.columns: Dict[str, self._Column] = {}  # type: ignore

    def __getattr__(self, attr) -> _Column:
        if attr not in self.columns:
            self.columns[attr] = self._Column(self.data_api, attr, self)
        return self.columns[attr]

    def fetch_data_timestamp(self, timestamp: pd.Timestamp) -> None:
        if self.scale in (TimeScale.MINUTE, TimeScale.DAILY):
            _df = get_symbol_data(
                self.data_api,
                self.symbol,
                start_date=(
                    timestamp.to_pydatetime()
                    - timedelta(
                        days=6 if self.scale == TimeScale.MINUTE else 120
                    )
                ).date(),
                end_date=(
                    timestamp.to_pydatetime() + timedelta(days=1)
                ).date(),
                scale="minute" if self.scale == TimeScale.MINUTE else "day",
            )
            self.symbol_data = pd.concat(
                [self.symbol_data, _df]
            ).drop_duplicates()
            # self.symbol_data = self.symbol_data[
            #    ~self.symbol_data.index.duplicated(keep="first")
            # ]

    def fetch_data_range(self, start: datetime, end: datetime) -> None:
        if self.scale in (TimeScale.MINUTE, TimeScale.DAILY):
            new_df = pd.DataFrame()
            while start < end:
                _df = get_symbol_data(
                    self.data_api,
                    self.symbol,
                    start_date=(
                        start
                        - timedelta(
                            days=2 if self.scale == TimeScale.MINUTE else 10
                        )
                    ).date(),
                    end_date=(start + timedelta(days=4)).date(),
                    scale="minute"
                    if self.scale == TimeScale.MINUTE
                    else "day",
                )
                new_df = pd.concat([new_df, _df]).drop_duplicates()
                start += timedelta(days=4)

            # new_df = new_df[~new_df.index.duplicated(keep="first")]
            self.symbol_data = pd.concat(
                [new_df, self.symbol_data]
            ).drop_duplicates()
            # self.symbol_data = self.symbol_data[
            #    ~self.symbol_data.index.duplicated(keep="first")
            # ]


class DataLoader:
    data: Dict[str, SymbolData] = {}

    def __init__(self, data_api: tradeapi, scale: TimeScale):
        self.data_api = data_api
        self.scale = scale

    def __getitem__(self, symbol: str) -> SymbolData:
        if symbol not in self.data:
            self.data[symbol] = SymbolData(self.data_api, symbol, self.scale)

        return self.data[symbol]
