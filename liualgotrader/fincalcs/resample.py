from enum import Enum

import pandas as pd


class ResampleRangeType(Enum):
    min_1 = 0
    min_2 = 1
    min_5 = 2
    min_10 = 3
    min_15 = 4


def resample(
    ohlc: pd.DataFrame, resample_range: ResampleRangeType
) -> pd.DataFrame:
    if ohlc.empty:
        return ohlc
    if resample_range == resample_range.min_1:
        return ohlc
    elif resample_range == resample_range.min_2:
        resample_str = "2min"
    elif resample_range == resample_range.min_5:
        resample_str = "5min"
    elif resample_range == resample_range.min_10:
        resample_str = "10min"
    elif resample_range == resample_range.min_15:
        resample_str = "15min"
    else:
        raise NotImplementedError(
            f"range type {resample_range} is not implemented"
        )

    close = ohlc.close.resample(resample_str).last()
    open = ohlc.open.resample(resample_str).first()
    high = ohlc.high.resample(resample_str).max()
    low = ohlc.low.resample(resample_str).min()
    volume = ohlc.volume.resample(resample_str).sum()

    return pd.concat(
        [
            open.rename("open"),
            high.rename("high"),
            low.rename("low"),
            close.rename("close"),
            volume.rename("volume"),
        ],
        axis=1,
    )
