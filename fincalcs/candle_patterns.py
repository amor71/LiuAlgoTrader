from typing import Tuple


def gravestone_doji(
    open: float, close: float, high: float, low: float
) -> bool:
    return (
        close == open and high > open and (close - low) * 1.2 < (high - close)
    )


def four_price_doji(
    open: float, close: float, high: float, low: float
) -> bool:
    return close == open == high == low


def doji(open: float, close: float, high: float, low: float) -> bool:
    return close == open and low <= open - 0.01 and high >= open + 0.01


def bull_spinning_top(
    open: float, high: float, low: float, close: float
) -> bool:
    upper_shadow = high - close
    lower_shadow = open - low
    shadow_size = upper_shadow + lower_shadow
    return (
        high > close > open > low
        and upper_shadow > 1.5 * lower_shadow
        and shadow_size > 3 * (close - high)
    )


def bull_spinning_top_bearish_followup(
    minute1: Tuple[float, float, float, float],
    minute2: Tuple[float, float, float, float],
) -> bool:
    return (
        bull_spinning_top(minute1[0], minute1[1], minute1[2], minute1[3])
        and minute2[0] > minute2[3]
    )
