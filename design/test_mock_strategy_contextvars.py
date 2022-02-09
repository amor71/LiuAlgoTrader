#! /usr/bin/env python3

import pytest
import mock_strategy_contextvars


@pytest.mark.parametrize(
    # testing parameters: symbol, position for False context,
    "bool_val, parameters", [(False, ('AAPL', 175.60))])
def test_set_context_False(bool_val, parameters):
    symbol, position = mock_strategy_contextvars.set_context(bool_val)
    assert symbol, position == parameters


@pytest.mark.parametrize(
    # testing return values for False context,
    "bool_val, return_val", [(False, tuple())])
def test_run_False(bool_val, return_val):
    symbol, position = mock_strategy_contextvars.set_context(bool_val)
    assert mock_strategy_contextvars.run(symbol, position) == return_val


@pytest.mark.parametrize(
    # testing parameters: symbol, position for True context,
    "bool_val, parameters", [(True, ({'AAPL': 175.60}, None))])
def test_set_context_True(bool_val, parameters):
    symbol, position = mock_strategy_contextvars.set_context(bool_val)
    assert symbol, position == parameters


@pytest.mark.parametrize(
    # testing return values for True context,
    "bool_val, return_val", [(True, dict())])
def test_run_True(bool_val, return_val):
    symbol, position = mock_strategy_contextvars.set_context(bool_val)
    assert mock_strategy_contextvars.run(symbol, position) == return_val
