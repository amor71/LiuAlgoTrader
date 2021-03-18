from liualgotrader.common import config
from liualgotrader.common.types import DataConnectorType, QueueMapper
from liualgotrader.data.alpaca import AlpacaData, AlpacaStream
from liualgotrader.data.data_base import DataAPI
from liualgotrader.data.polygon import PolygonData, PolygonStream
from liualgotrader.data.streaming_base import StreamingAPI


def data_loader_factory() -> DataAPI:
    if config.data_connector == DataConnectorType.polygon:
        return PolygonData()
    elif config.data_connector == DataConnectorType.alpaca:
        return AlpacaData()
    else:
        raise Exception(f"unsupported data provider {config.data_connector}")


def streaming_factory():
    if config.data_connector == DataConnectorType.polygon:
        return PolygonStream
    elif config.data_connector == DataConnectorType.alpaca:
        return AlpacaStream
    else:
        raise Exception(
            f"unsupported streaming provider {config.data_connector}"
        )
