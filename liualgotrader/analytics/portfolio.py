import alpaca_trade_api as tradeapi
from pandas import DataFrame

from liualgotrader.common.decorators import timeit
from liualgotrader.common.market_data import latest_stock_price
from liualgotrader.models.portfolio import Portfolio


@timeit
async def load(data_api: tradeapi, portfolio_id: str) -> DataFrame:
    df = await Portfolio.load(portfolio_id)

    for i, row in df.iterrows():
        df.loc[df.symbol == row.symbol, "price"] = latest_stock_price(
            data_api=data_api, symbol=row.symbol
        )

    return df
