#! /usr/bin/env python3

import contextvars
symbol = 'AAPL'
position = 175.60
symbols_position = {'AAPL': 175.60}

# parameters
var1 = contextvars.ContextVar('symbol', default=symbol)
var2 = contextvars.ContextVar('position', default=position)
# return value
var3 = contextvars.ContextVar('return_val', default=tuple())


def run(symbol, position):
    '''functions can return  Dictionary with symbol and 'actions'
    -> Dict[str, Dict] or tuple of a boolean and dictionary
    -> Tuple[bool, Dict]'''

    return var3.get()


# setting context for contextvars
def set_context(bool_val):
    ''' call to set a new value for the context variable
    in the current context'''

    if should_run_all(bool_val):
        var1.set(symbols_position)
        var2.set(None)
        var3.set(dict())
    symbol = var1.get()
    position = var2.get()

    return symbol, position


def should_run_all(bool_val):
    '''The Platform decides which function to call,
    based on the value returned by should_run_all()'''

    return bool_val
