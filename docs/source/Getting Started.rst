Getting Started
===============

*"All Beginings are Hard"*
**************************
    -- *nobody ever*

Step 1
------

First, lets get you up to speed w/ the constructs & terminology. 
The following diagram outlines the main constructs which are detailed in the 
`Concepts` section of this documentation.

.. image:: /images/conceptual_model.png
    :width: 1000
    :align: left
    :alt: liu concepts

In a nutshell:
* An Account holds cash-balance for Portfolio(s),
* A Portfolio tracks trades over time (=batches),
* A Batch is an execution of liu Framework during a specific trading day, 
* During an exeuction of the framework, strategies trade securities as part of a daily batch.

Step 1.5
--------

Digging further down, your trading day is made of two parts: 

1. Stock Selection, a.k.a *Scanners*, 
2. Executing *Strategies* on picked stocks.

Scanners feed Strategies to securities to act (or not act) upon. Scanners can return a 
fixed list of stocks, or dynamicly calculate in real-time. You can define execution Windows for 
scanners, as well as thier execution frequency within the selected windows.

Step 1.75
---------
Once you understand these bascis, the next step is to understand the mechanics of 
running definition an exeuction (either trading, or back-testing). `LiuAlgoTrader` uses
JSON-like **TOML** file format for specifying which Scanners and Strategies to run.

Don't Panic!
------------

Do you already have liu installed and configured? **That's Awesome!**
If you havn't done so yet, jump to the `Quickstart` section to get the platform up and running,
then get back here with us cool cats.

When you are ready to proceed, below is a recommanded order of reading the rest of the documentation:

1. Read the `Configuration` section to understand more on the `tradeplan.toml` mechanics,
2. `Concepts` section is detailed-packed, skim over it in your first time read,
3. `Scanners` section comes next, followed by `Strategies`
4. When ready read the `back-testing` section (note it's marked in Bold)

Now would be a good time to start writing your first strategy/scanner and take liu for a test-drive. 

Resources
---------

If you hit a road-block, or something is not clear, check out:

*  The issues_ section on GitHub

.. _issues: 
    https://github.com/amor71/LiuAlgoTrader/issues

* You can always message me on the liu Glitter_ chat room, and I'll do my best to help.

.. _Glitter:
    https://gitter.im/LiuAlgoTrader/community







