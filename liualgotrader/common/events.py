from typing import Dict

from liualgotrader.common import config


class Event:
    def __init__(self, payload: Dict):
        self.payload: Dict = payload


class TraceableEvent(Event):
    def __init__(self, payload: Dict):
        super().__init__(payload=payload)


class EventFactory:
    @staticmethod
    def get_instance(cls) -> object:
        return TraceableEvent if config.trace_enabled else Event
