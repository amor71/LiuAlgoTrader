from liualgotrader.common import config
from liualgotrader.common.types import DataConnectorType
from liualgotrader.data.alpaca import AlpacaData
from liualgotrader.data.data_base import DataAPI
from liualgotrader.data.polygon import PolygonData


def data_loader_factory() -> DataAPI:
    if config.data_connector == DataConnectorType.polygon:
        return PolygonData()
    elif config.data_connector == DataConnectorType.alpaca:
        return AlpacaData()
    else:
        raise Exception(f"unsupported data prodvider {config.data_connector}")
