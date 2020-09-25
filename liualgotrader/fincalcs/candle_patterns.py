from typing import Tuple


def gravestone_doji(open: float, high: float, low: float, close: float) -> bool:
    open = round(open, 2)
    high = round(high, 2)
    low = round(low, 2)
    close = round(close, 2)

    body_size = close - open if close > open else open - close
    upper_shadow = high - max(close, open)
    lower_shadow = min(close, open) - low
    shadow_size = upper_shadow + lower_shadow

    return (
        body_size < 0.02 < shadow_size
        and lower_shadow * 2 < upper_shadow
        and shadow_size > 2 * body_size
    )


def four_price_doji(open: float, close: float, high: float, low: float) -> bool:
    open = round(open, 2)
    high = round(high, 2)
    low = round(low, 2)
    close = round(close, 2)

    return close == open == high == low


def doji(open: float, close: float, high: float, low: float) -> bool:
    open = round(open, 2)
    high = round(high, 2)
    low = round(low, 2)
    close = round(close, 2)

    return close == open and low <= open - 0.01 and high >= open + 0.01


def spinning_top(open: float, high: float, low: float, close: float) -> bool:
    open = round(open, 2)
    high = round(high, 2)
    low = round(low, 2)
    close = round(close, 2)

    upper_shadow = high - max(close, open)
    lower_shadow = min(close, open) - low
    shadow_size = upper_shadow + lower_shadow
    body_size = close - open if close > open else open - close
    return (
        shadow_size >= 2 * body_size
        and lower_shadow > 0.02
        and upper_shadow > 0.02
        and 0.8 < upper_shadow / lower_shadow < 1.2
    )


def bullish_candle(open: float, high: float, low: float, close: float) -> bool:
    open = round(open, 2)
    high = round(high, 2)
    low = round(low, 2)
    close = round(close, 2)

    upper_shadow = high - close
    lower_shadow = open - low
    shadow_size = upper_shadow + lower_shadow
    body_size = close - open

    return close > open + 0.02 and body_size > shadow_size * 1.2


def bearish_candle(open: float, high: float, low: float, close: float) -> bool:
    open = round(open, 2)
    high = round(high, 2)
    low = round(low, 2)
    close = round(close, 2)

    body_size = close - open if close > open else open - close

    return close < open and body_size >= 0.01


def dragonfly_candle(open: float, high: float, low: float, close: float) -> bool:
    open = round(open, 2)
    high = round(high, 2)
    low = round(low, 2)
    close = round(close, 2)

    upper_shadow = high - max(close, open)
    lower_shadow = min(close, open) - low
    shadow_size = upper_shadow + lower_shadow
    body_size = close - open if close > open else open - close

    return (
        body_size < 0.01
        and lower_shadow > 2 * upper_shadow
        and shadow_size > 3 * body_size
    )


def spinning_top_bearish_followup(
    minute1: Tuple[float, float, float, float],
    minute2: Tuple[float, float, float, float],
) -> bool:
    return (
        spinning_top(minute1[0], minute1[1], minute1[2], minute1[3])
        and minute2[0] > minute2[3]
    )


def bullish_candle_followed_by_dragonfly(
    minute1: Tuple[float, float, float, float],
    minute2: Tuple[float, float, float, float],
) -> bool:
    return (
        bullish_candle(minute1[0], minute1[1], minute1[2], minute1[3])
        and dragonfly_candle(minute2[0], minute2[1], minute2[2], minute2[3])
        and minute2[0] > minute1[3]
    )
