import asyncio
import itertools
import uuid
from typing import List

from liualgotrader.common.database import create_db_connection
from liualgotrader.models.portfolio import Portfolio


class Hyperparameter:
    def __init__(
        self, name, param_type, initial_value=None, last_value=None, **kwargs
    ):
        self.name = name
        self.param_type = param_type

        if initial_value:
            self.initial_value = initial_value

        if last_value:
            self.last_value = last_value

        self.value = None

        for key in kwargs:
            if not hasattr(self, key):
                setattr(self, key, kwargs[key])

    def __repr__(self):
        return self.name

    def __iter__(self):
        self.value = None
        return self

    def __next__(self):
        if hasattr(self, "last_value") and self.value == self.last_value:
            raise StopIteration

        if self.param_type == int:
            self.value = (
                self.param_type(self.initial_value)
                if not self.value
                else self.value + 1
            )
        elif self.param_type == "portfolio":
            amount = getattr(self, "size")
            credit = getattr(self, "credit", 0)

            if asyncio.get_event_loop().is_closed():
                loop = asyncio.new_event_loop()
                loop.run_until_complete(create_db_connection())
            else:
                loop = asyncio.get_event_loop()

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
        else:
            raise NotImplementedError(
                f"Hyperparameter for type {self.param_type} is not implemented yet"
            )

        return (self.name, self.value)


class Hyperparameters:
    def __init__(self, hyperparameters: List[Hyperparameter]):
        self.hyperparameters = hyperparameters

    def __iter__(self):
        yield from itertools.product(*self.hyperparameters)
