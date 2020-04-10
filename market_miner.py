import asyncio
import os

import alpaca_trade_api as tradeapi
import pygit2

import config
from common.decorators import timeit
from common.tlog import tlog


@timeit
async def update_all_tickers_data(api: tradeapi) -> None:
    pass


def motd(filename: str, version: str) -> None:
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
    asyncio.ensure_future(update_all_tickers_data(data_api))

    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        tlog(f"Caught KeyboardInterrupt")
    except Exception as e:
        tlog(f"Caught exception {str(e)}")


"""
starting
"""
build_label = pygit2.Repository("./").describe()
filename = os.path.basename(__file__)
motd(filename=filename, version=build_label)

main()
tlog("Done.")
