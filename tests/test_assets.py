import pytest

from liualgotrader.common import assets


@pytest.mark.devtest
def test_round_asset() -> bool:
    f = 0.999349343434
    print(f, assets.round_asset("BTCUSD", f))

    return True
