from liualgotrader.common import config
from liualgotrader.common.types import DataConnectorType
from liualgotrader.data.alpaca import AlpacaData, AlpacaStream
from liualgotrader.data.data_base import DataAPI
from liualgotrader.data.finnhub import FinnhubData
from liualgotrader.data.polygon import PolygonData, PolygonStream


def data_loader_factory(connector: DataConnectorType = None) -> DataAPI:
    _connector = connector or config.data_connector
    if _connector == DataConnectorType.polygon:
        return PolygonData()
    elif _connector == DataConnectorType.alpaca:
        return AlpacaData()
    elif _connector == DataConnectorType.finnhub:
        return FinnhubData()
    else:
        raise Exception(f"unsupported data provider {config.data_connector}")


def streaming_factory(connector: DataConnectorType = None):
    _connector = connector or config.data_connector
    if _connector == DataConnectorType.polygon:
        return PolygonStream
    elif _connector == DataConnectorType.alpaca:
        return AlpacaStream
    else:
        raise Exception(
            f"unsupported streaming provider {config.data_connector}"
        )
