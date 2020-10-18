.. _`How to Install & Setup`:

How to Install & Setup
======================

This section describes the sets and processes to
install and setup `LiuAlgoTrader` for first use. If it relevant mostly if you didn't go through the `Quickstart` wizard or would like to use an existing / cloud-base database.

Prerequisite
------------
- Paper, and preferable a funded Live account with `Alpaca Markets`_
- Installed PostgreSQL_ database.

.. _Alpaca Markets: https://alpaca.markets/docs/about-us/
.. _PostgreSQL: https://www.postgresql.org/


Installation
------------

To install LiuAlgoTrader just type:

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

The following SQL script may be used to create the required database schema to LiuAlgoTrader needs:

.. literalinclude:: ../../database/schema.sql
  :language: SQL
  :linenos:

the latest schema file can be found in the `database` folder in LiuAlgoTrader distribution , it is recommended to always use the latest DB schema file,
which is backward compatible and executing the scripts will automatically
migrate the data to the latest version.

Data Providers
--------------
Algorithmic trading is only as good as the data feed it rely on.
Without an accurate, near-real-time data feed even the
best strategy will keep losing money.

Luckily, Alpaca is well integrated with `Polygon.io`_ for free.
A funded Alpaca account is granted an access to Polygon live data streaming,
which is mostly accurate. A non-funded account has access only to Alpaca
paper-data which is less accurate, but okay-ish to start with.

LiuAlgoTrader also support Finnhub_ as a data-source.

.. _Polygon.io: https://polygon.io/
.. _Finnhub: https://finnhub.io/dashboard


Example Setup on GCP
--------------------
Alpaca Markets seems to be hosted on GCP us-east4-c,
while Polygon.io is hosted in Equinix. It is a good idea to locate
the trading servers close to the brokerage servers to best
execution times.

While you may run LiuAlgoTrader on your home desktop or
laptop, having a hosted service, even a lean one could
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
Your total monthly bill should be around $50/month while
consuming the logging services.



