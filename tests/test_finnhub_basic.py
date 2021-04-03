from datetime import date, datetime

import pandas as pd
import pytest

from liualgotrader.common import config
from liualgotrader.data.finnhub import FinnhubData


@pytest.mark.devtest
def test_create_finnhub() -> bool:
    finnhub = FinnhubData()
    print(finnhub.stock_exchanges)
    return True
