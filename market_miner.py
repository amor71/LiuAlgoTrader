import os

import alpaca_trade_api as tradeapi
import pygit2

import config
from tlog import tlog


async def update_all_tickers_data(api: tradeapi):
    pass


def motd(filename: str, version: str):
    """Display welcome message"""

    print("+=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=+")
    tlog(f"{filename} {version} starting")
    print("+=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=+")


def main():
    data_api = tradeapi.REST(
        base_url=config.prod_base_url,
        key_id=config.prod_api_key_id,
        secret_key=config.prod_api_secret,
    )
    update_all_tickers_data(data_api)


"""
starting
"""
build_label = pygit2.Repository("./").describe()
filename = os.path.basename(__file__)
motd(filename=filename, version=build_label)

main()
tlog("Done.")
