.. _`How to Install & Setup`:

Advanced Setup
==============

This section describes the steps to
install and setup `LiuAlgoTrader` for first time use on a pre-existing PostgreSQL database installation. The section is mostly relevant for users that did not go through the `Quickstart` wizard.

Prerequisite
------------
- Paper, or a funded Live account with `Alpaca Markets`_ ,
- Developer subscription w/ Polygon_ ,
- An Installed and configured PostgreSQL_ database.

.. _Alpaca Markets: https://alpaca.markets/docs/about-us/
.. _PostgreSQL: https://www.postgresql.org/
.. _Polygon: https://polygon.io/

**NOTE:** Alpaca only version coming soon,

Installation
------------

To install LiuAlgoTrader type:

.. code-block:: bash

   pip install liualgotrader


Database Setup
--------------

LiuAlgoTrader applications persist trade details to a relational database.
The applications are developed on-top of PostgreSQL_, however the code may be adopted to use any SQL-supported database .


The database is mostly used for storing trade details, including stock name, price, quantity,
indicators and more. This data is valuable when analysing the trading day,
and improving the algorithmic strategies. For further reading, see Understanding the Data Model.

Database Connection
*******************

The **DSN** environment variable holds the connection string to the database. For example:

.. code-block:: bash

    export DSN="postgresql://momentum@localhost/tradedb"

To `learn more`_ on how to select your connection string.

.. _learn more: https://www.postgresql.org/docs/9.3/libpq-connect.html#LIBPQ-CONNSTRING


Database Schema script
**********************

The following SQL script creates the required database schema:

.. literalinclude:: ../../database/schema.sql
  :language: SQL
  :linenos:


**NOTE**:
When updating from a predecessor version of `LiuAlgoTrader`, it is recommended to re-run the database script.
the latest schema file can be found in the `database` folder in LiuAlgoTrader distribution.
The script is backward compatible and executing the scripts will automatically
migrate the data to the latest version.

Data Providers
--------------
Algorithmic trading is only as good as the data feed it rely on.
Without an accurate, near-real-time data feed even the
best strategy will keep losing money.

LiuAlgoTrader currently support Polygon.io as a data-provider, 
while Alapaca native data integration is underway, as well as Finnhub_.

.. _Finnhub: https://finnhub.io/dashboard


Example Setup on GCP
--------------------
Alpaca Markets seems to be hosted on GCP us-east4-c,
while Polygon.io is hosted in Equinix. It is a good idea to locate
the trading servers close to the brokerage servers to best
execution times.

While you may run LiuAlgoTrader on your home desktop or
laptop, having a hosted server, even a lean one could
help the consistency of your trades.

The steps for basic hosting on Google Cloud Platform:

1. In the `SQL` section create an instance of PostgreSQL,
this would be a fully hosted service. Minimal
configuration should be enough to start with, though
high-availability & daily backup of the database is
recommended.

2. In the `Compute Engine` create a `VM Instance`, the
smallest (g1-small) should be OK to start with.
Even though its a single CPU, running multiple LiuAlgo
Trader processes would be able to trade > 400 concurrent
stock without saturating the computation resources.

3. Install locally the `gcloud` CLI, connect to your
remote instance create a folder to contain your credentials for
connecting with other GCP services, as well as install
your database private keys.

4. Connect to the database, and run the schema script.
If you're developing remotely, make sure to install the
tunnel to your database from your local machine.

You're now ready to run LiuAlgoTrader in the cloud.
Your total monthly bill should be around $70/month while
consuming the logging services.



