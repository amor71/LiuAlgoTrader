from dataclasses import dataclass


@dataclass
class TickerSnapshot:
    symbol: str
    volume: int
    today_change: float
