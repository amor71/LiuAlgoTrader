import pandas as pd
import pytest

from liualgotrader.common.hyperparameter import Hyperparameter, Hyperparameters


def test_hyper_param_1():
    p1 = Hyperparameter(int, 5, 6)

    a2 = next(p1)

    if a2 != 5:
        raise AssertionError(f"Hyperparameter of int expected 5 got {a2}")

    a3 = next(p1)
    if a3 != 6:
        raise AssertionError(f"Hyperparameter of int expected 6 got {a3}")

    return True


def test_hyper_param_1_ex():
    p1 = Hyperparameter(int, 5, 5)

    a2 = next(p1)

    if a2 != 5:
        raise AssertionError(f"Hyperparameter of int expected 5 got {a2}")

    try:
        a3 = next(p1)
    except StopIteration:
        return True

    raise AssertionError(f"Expected Exception StopIteration, but got {a3}")


def test_hyper_params_1():
    p1 = Hyperparameter(int, 5, 7)
    h = Hyperparameters([p1])

    for i in iter(h):
        print(i)

    return True


def test_hyper_params_2():
    p1 = Hyperparameter(int, 5, 7)
    p2 = Hyperparameter(int, 8, 17)

    h = Hyperparameters([p1, p2])

    for i in iter(h):
        print(i)

    return True
