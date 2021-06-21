import pandas as pd
import pytest

from liualgotrader.common.hyperparameter import Hyperparameter, Hyperparameters


def test_hyper_param_1():
    p1 = Hyperparameter("p1", int, 5, 6)

    _ = next(p1)
    _ = next(p1)

    return True


def test_hyper_param_single():
    p1 = Hyperparameter("p1", int, 5, 5)

    print("single", next(p1))

    return True


def test_hyper_param_1_ex():
    p1 = Hyperparameter("p1", int, 5, 5)

    next(p1)

    try:
        a3 = next(p1)
    except StopIteration:
        return True

    raise AssertionError(f"Expected Exception StopIteration, but got {a3}")


def test_hyper_params_1():
    p1 = Hyperparameter("p1", int, 5, 7)
    h = Hyperparameters([p1])

    for i in iter(h):
        print(i)

    return True


def test_hyper_params_2():
    p1 = Hyperparameter("p1", int, 5, 7)
    p2 = Hyperparameter("p2", int, 8, 17)

    h = Hyperparameters([p1, p2])

    for i in iter(h):
        print(i)

    return True
