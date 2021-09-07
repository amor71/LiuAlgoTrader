**Quickstart**
==============

Prerequisite
------------

1. Paper, or a funded account with Alpaca_ Markets, 

.. _Alpaca: https://alpaca.markets/docs/about-us


2. Installed Docker Engine_ and,

.. _Engine: https://docs.docker.com/engine/install

3. Docker Compose_

.. _Compose: https://docs.docker.com/compose/install/


Touch & Go
----------

**NOTE** for Windows_ users

.. _Windows: https://liualgotrader.readthedocs.io/en/latest/Troubleshooting.html#q-can-i-run-liu-on-windows

**Step 1**: install LiuAlgoTrader

.. code-block:: bash

   pip install liualgotrader

Having issues on installation? Check out the installation FAQ_

.. _FAQ: https://liualgotrader.readthedocs.io/en/latest/Troubleshooting.html

**Step 2**: Run the setup wizard

.. code-block:: bash

   liu quickstart

Follow the installation wizard instructions. The wizard will walk you
through the configuration of environment variables, setup of a locally
dockerized PostgreSQL that is pre-populated with test data:

.. image:: /images/liu-wizard.png
    :width: 800
    :align: left
    :alt: liu setup wizard


First time use
--------------

LiuAlgoTrader `quickstart` wizard installs samples allowing a first-time experience of the framework. Follow the post-installation instructions, and try to back-test a specific day.

if you follow the installation till the end, the wizard will walk you through how to run the back-test UI:

.. code-block:: bash

    streamlit run https://raw.github.com/amor71/LiuAlgoTrader/master/analysis/backtester_ui.py

Once executed, your screen should look like this:

.. image:: /images/liu-firsttime.png
    :width: 800
    :align: left
    :alt: liu first time use


Select the `Analyzer` app on the upper-right drop-down and enter
'2398380c-5146-4b58-843a-a50c458c8071' as a pre-loaded batch-id.

`Voila!`
^^^^^^^^
You should see a pre-loaded session from your local database.
You're all set now.

**NOTE**

Unlike back-testing a specific trading session, back-testing a whole day
requires downloading data from Polygon.io into your local database. This is done once, per date, and may take minutes to an hour depending on your connection type.

What's Next?
------------

Read through the rest of the documentation, starting with the 'Getting Started' section. Understand the framework concepts, create your own strategies and run a trading session.