from liualgotrader.common import config
from liualgotrader.common.types import DataConnectorType
from liualgotrader.data_stream.base import DataAPI
from liualgotrader.data_stream.polygon import Polygon


def data_loader_factory() -> DataAPI:
    if config.data_connector == DataConnectorType.polygon:
        return Polygon()
    else:
        raise Exception(f"unsupported data prodvider {config.data_connector}")
