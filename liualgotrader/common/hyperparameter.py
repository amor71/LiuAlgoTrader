import asyncio
import itertools
import uuid
from typing import List

from liualgotrader.common.database import create_db_connection
from liualgotrader.models.portfolio import Portfolio


class Parameter:
    def __init__(self, name, param_type, min=None, max=None, **kwargs):
        self.name = name
        self.param_type = param_type

        if min:
            self.initial_value = min

        if max:
            self.last_value = max

        self.value = None

        for key in kwargs:
            if not hasattr(self, key):
                setattr(self, key, kwargs[key])

    def __repr__(self):
        return self.name

    def __iter__(self):
        self.value = None
        return self

    def __call__(self):
        if self.param_type != "portfolio":
            raise NotImplementedError(
                f"Parameter for type {self.param_type} is not implemented yet"
            )

        amount = getattr(self, "size")
        credit = getattr(self, "credit", 0)

        if asyncio.get_event_loop().is_closed():
            loop = asyncio.new_event_loop()
        else:
            loop = asyncio.get_event_loop()

        loop.run_until_complete(create_db_connection())
        portfolio_id = str(uuid.uuid4())
        loop.run_until_complete(
            Portfolio.save(
                portfolio_id=portfolio_id,
                portfolio_size=amount,
                credit=credit,
                parameters={},
            )
        )
        self.last_value = self.value = portfolio_id
        return (self.name, self.value)

    def __next__(self):
        if hasattr(self, "last_value") and self.value == self.last_value:
            raise StopIteration

        if self.param_type in ("int", int):
            self.value = (
                int(self.initial_value) if not self.value else self.value + 1
            )
        elif self.param_type in (float, "float"):
            if not hasattr(self, "delta"):
                raise AttributeError(
                    f"midding `delta` parameter for hyper-parameter {self.name}"
                )
            self.value = (
                float(self.initial_value)
                if not self.value
                else self.value + self.delta
            )
        else:
            raise NotImplementedError(
                f"Parameter for type {self.param_type} is not implemented yet as iterator"
            )

        return (self.name, self.value)


class Hyperparameters:
    def __init__(self, hyperparameters: List[Parameter]):
        self.hyperparameters = hyperparameters

    def __iter__(self):
        yield from itertools.product(*self.hyperparameters)
