Getting Started
===============

*"All Beginings are Hard"*
**************************
    -- *nobody ever*

Step 1
------

First, lets get you up to speed with the constructs & terminology.
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
* During an execution of the framework, strategies trade securities as part of a daily batch.

Step 1.5
--------

Digging deeper, your trading day is made of two parts:

1. Stock Selection, a.k.a *Scanners*, 
2. Executing *Strategies* on picked stocks.

Scanners feed Strategies a list of securities for them to act (or not act) upon. The list of stocks returned by
Scanners can either be fixed or dynamic over time. You can define execution Windows for
scanners, as well as their execution frequency within the selected windows.

Step 1.75
---------
Once you understand these basics, the next step is to understand the mechanics of
running an execution (either trading, or back-testing). `LiuAlgoTrader` uses
JSON-like **TOML** file format to specify Scanners and Strategies for execution.

Don't Panic!
------------

Do you already have liu installed and configured? **That's Awesome!**
If you haven't done so yet, jump to the `Quickstart` section to get the platform up and running,
then get back here with us cool cats.

When you are ready, below is a recommended order for reading the rest of the documentation:

1. Read the `Configuration` section to understand more on the structure of `tradeplan.toml`,
2. `Concepts` section is detailed-packed, recommended to skim through it in your first read,
3. `Scanners` section comes next, followed by `Strategies`
4. When ready read the `back-testing` section (note it's marked in Bold)

As a next step, it's time to start writing your first strategy/scanner and take liu for a test-drive.

Resources
---------

If you hit a road-block, or something is not clear, check out:

*  The issues_ section on GitHub

.. _issues: 
    https://github.com/amor71/LiuAlgoTrader/issues

* You can always message me on the liu Glitter_ chat room, and I'll do my best to help.

.. _Glitter:
    https://gitter.im/LiuAlgoTrader/community







