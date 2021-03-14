Quickstart
==========

Prerequisite
------------

1. Paper, or a funded account with Alpaca_ Markets, 

.. _Alpaca: https://alpaca.markets/docs/about-us


2. Developer subscription w/ Polygon_ 

.. _Polygon: https://polygon.io/

3. Installed Docker Engine_ and,

.. _Engine: https://docs.docker.com/engine/install

4. Docker Compose_

.. _Compose: https://docs.docker.com/compose/install/

**NOTE:** Alpaca only version coming soon,

Touch & Go
----------

**Step 1**: install LiuAlgoTrader

.. code-block:: bash

   pip install liualgotrader

**Step 2**: Run the setup wizard

.. code-block:: bash

   liu quickstart

Follow the installation wizard instructions. The wizard will walk you
through the configuration of environment variables, setup of a local
dockerized PostgreSQL and pre-populate with test data:

.. image:: /images/liu-wizard.png
    :width: 800
    :align: left
    :alt: liu setup wizard


First time use
--------------

LiuAlgoTrader `quickstart` wizard installs samples allowing a first-time experience of the framework. Follow the post-installation instructions, and try to back-test a specific day.

if you follow the installation till the end, the wizard will direct you how to run the back-test UI:

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
You should be now seeing a pre-loaded session from your local database.
You're all set now.

**NOTE**

back-testing a whole day, unlike back-testing a specific trading session
requires downloading of data from Polygon.io into your local database. This is done one time, per date, and may take few minutes to an hour depending on your connection type.

What's Next?
------------

Read through the rest of the documentation, understand the framework concepts, create your on strategies and run a trading session with LiuAlgoTrading Framework.