import asyncio

import pytz

from liualgotrader.analytics.analysis import load_trades_by_portfolio
from liualgotrader.models.accounts import Accounts
from liualgotrader.models.portfolio import Portfolio


async def _calc_account_transactions(portfolio_id: str, account_id: int):
    _df = load_trades_by_portfolio(portfolio_id)
    local = pytz.timezone("UTC")
    for _, row in _df.iterrows():
        utc_dt = local.localize(row.tstamp, is_dst=None)
        await Accounts.add_transaction(
            account_id,
            (row.qty * row.price) * (-1 if row.operation == "buy" else 1),
            utc_dt,
        )


def account_transactions(portfolio_id: str):
    loop = asyncio.get_event_loop()
    _ = loop.run_until_complete(Portfolio.load_by_portfolio_id(portfolio_id))
    account_id, account_size = loop.run_until_complete(
        Portfolio.load_details(portfolio_id)
    )
    loop.run_until_complete(Accounts.clear_balance(account_id, account_size))
    loop.run_until_complete(Accounts.clear_account_transactions(account_id))

    loop.run_until_complete(
        _calc_account_transactions(
            portfolio_id=portfolio_id, account_id=account_id
        )
    )
