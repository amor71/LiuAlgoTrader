import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from json.decoder import JSONDecodeError
from typing import Dict, List, Optional

import requests
from alpaca_trade_api.common import get_polygon_credentials
from alpaca_trade_api.polygon.entity import Ticker

from liualgotrader.common import config
from liualgotrader.common.decorators import timeit
from liualgotrader.common.tlog import tlog
from liualgotrader.miners.base import Miner
from liualgotrader.models.ticker_data import TickerData


class StockCluster(Miner):
    def __init__(self):
        self._num_workers = 20
        super().__init__(name="StockCluster")

    @property
    def num_workers(self):
        return self._num_workers

    @num_workers.setter
    def num_workers(self, new_num_workers: int):
        if new_num_workers <= 0 or new_num_workers > 100:
            raise ValueError("number of workers must be positive and less than 100")

    @timeit
    async def run(self) -> bool:
        tickers = []

        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            with requests.Session() as session:
                count = self._get_count(session)
                loop = asyncio.get_event_loop()
                tasks = [
                    loop.run_in_executor(executor, self._fetch, *(session, page))
                    for page in range(1, count // 50 + 1)
                ]
                for response in await asyncio.gather(*tasks):
                    tickers += response
        tlog(f"loaded {len(tickers)} tickers")

        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            with requests.Session() as session:
                loop = asyncio.get_event_loop()

                tasks = [
                    loop.run_in_executor(
                        executor,
                        self._fetch_symbol_details,  # type: ignore
                        *(session, ticker),
                    )
                    for ticker in tickers
                ]
                info = [
                    response
                    for response in await asyncio.gather(*tasks)
                    if response is not None
                ]
        tlog(f"loaded {len(info)} ticker details")
        await asyncio.gather(*[self._update_ticker_details(i) for i in info])

        return True

    def _get_count(self, session) -> int:
        url = "https://api.polygon.io/" + "v2" + "/reference/tickers"
        with session.get(
            url,
            params={
                "apiKey": get_polygon_credentials(config.prod_api_key_id),
                "market": "STOCKS",
                "page": 1,
                "active": "true",
                "perpage": 1,
            },
        ) as response:
            return response.json()["count"]

    def _fetch(self, session: requests.Session, page: int) -> List[Ticker]:
        url = "https://api.polygon.io/" + "v2" + "/reference/tickers"
        try:
            with session.get(
                url,
                params={
                    "apiKey": get_polygon_credentials(config.prod_api_key_id),
                    "market": "STOCKS",
                    "page": page,
                    "active": "true",
                    "perpage": 50,
                },
            ) as response:
                data = response.json()["tickers"]
                return [Ticker(x) for x in data]
        except requests.exceptions.ConnectionError as e:
            tlog(
                f"_fetch(): got HTTP exception {e}, for {page}, going to sleep, then retry"
            )
            time.sleep(30)
            return self._fetch(requests.Session(), page)

    async def _update_ticker_details(self, ticker_info: Dict) -> None:
        if ticker_info["active"] is False:
            return

        ticker_data = TickerData(
            name=ticker_info["name"],
            symbol=ticker_info["symbol"],
            description=ticker_info["description"],
            tags=ticker_info["tags"],
            similar_tickers=ticker_info["similar"],
            industry=ticker_info["industry"],
            sector=ticker_info["sector"],
            exchange=ticker_info["exchange"],
        )

        if await ticker_data.save(config.db_conn_pool) is False:
            tlog(f"going to wait 30 seconds and retry saving {ticker_info['name']}")
            await asyncio.sleep(30)
            return await self._update_ticker_details(ticker_info)

    def _fetch_symbol_details(
        self, session: requests.Session, ticker: Ticker
    ) -> Optional[Dict]:
        url = (
            "https://api.polygon.io/" + "v1" + f"/meta/symbols/{ticker.ticker}/company"
        )

        try:
            with session.get(
                url,
                params={"apiKey": get_polygon_credentials(config.prod_api_key_id)},
            ) as response:
                if response.status_code == 200:
                    try:
                        r = response.json()
                        if r["active"]:
                            return r
                    except JSONDecodeError:
                        tlog(f"JSONDecodeError for {ticker.ticker}")
                        raise Exception(response.text)

        except requests.exceptions.ConnectionError as e:
            tlog(
                f"_fetch_symbol_details(): got HTTP exception {e} for {ticker.ticker}, going to sleep, then retry"
            )
            time.sleep(30)
            return self._fetch_symbol_details(requests.Session(), ticker)

        return None
