import os

os.environ["DATA_CONNECTOR"] = "alpaca"

import pytest

from liualgotrader.analytics import analysis


@pytest.mark.devtest
def test_returns() -> bool:
    td = analysis.calc_batch_returns("0664dc2c-f126-4c7f-a069-c5dc246e2df4")
    print(td)
    return True


@pytest.mark.devtest
async def test_load_trades_by_portfolio():
    trades = analysis.load_trades_by_portfolio(
        "71f0eaa7-281a-40ad-b120-d2f74eb0b05d"
    )
    print(trades)

    return True
