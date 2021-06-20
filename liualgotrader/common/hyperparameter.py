import itertools
from typing import List


class Hyperparameter:
    def __init__(self, name, param_type, initial_value, last_value):
        self.name = name
        self.param_type = param_type
        self.initial_value = initial_value
        self.last_value = last_value
        self.value = None

    def __repr__(self):
        return self.name

    def __iter__(self):
        self.value = None
        return self

    def __next__(self):
        if self.value == self.last_value:
            raise StopIteration

        if self.param_type == int:
            self.value = (
                self.param_type(self.initial_value)
                if not self.value
                else self.value + 1
            )
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
