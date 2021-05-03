import asyncio
from datetime import date

import pandas as pd
import pytest

from liualgotrader.analytics import analysis
from liualgotrader.common.database import create_db_connection


@pytest.mark.devtest
def test_soyreturns() -> bool:
    td = analysis.compare_to_symbol_returns(
        "0664dc2c-f126-4c7f-a069-c5dc246e2df4", "SPY"
    )
    print(td)
    return True


@pytest.mark.devtest
def test_returns() -> bool:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_db_connection())
    td = analysis.calc_batch_returns("0664dc2c-f126-4c7f-a069-c5dc246e2df4")
    print(td)
    return True
