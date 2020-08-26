How to Install & Setup
======================

This section describes the sets and processes to install and setup LiuAlgoTrader for first use.

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

To `learn more`_ on how to select your connection stream.

.. _learn more: https://www.postgresql.org/docs/9.3/libpq-connect.html#LIBPQ-CONNSTRING


Database Schema script
**********************

The following SQL script may be used to create the required database schema to LiuAlgoTrader needs:

.. code-block:: SQL

    CREATE TYPE trade_operation AS ENUM ('buy', 'sell');
    CREATE TYPE trade_env AS ENUM ('PAPER', 'PROD');
    CREATE SEQUENCE IF NOT EXISTS transaction_id_seq START 1;
    CREATE TABLE IF NOT EXISTS algo_run (
        algo_run_id serial PRIMARY KEY,
        algo_name text NOT NULL,
        algo_env text NOT NULL,
        build_number text NOT NULL,
        parameters jsonb,
        start_time timestamp DEFAULT current_timestamp,
        end_time timestamp,
        end_reason text
    );
    CREATE TABLE IF NOT EXISTS trades (
        trade_id serial PRIMARY KEY,
        algo_run_id integer REFERENCES algo_run(algo_run_id),
        is_win bool,
        symbol text NOT NULL,
        qty integer NOT NULL check (qty > 0),
        buy_price decimal (8, 2) NOT NULL,
        buy_indicators jsonb NOT NULL,
        buy_time timestamp DEFAULT current_timestamp,
        sell_price decimal (8, 2),
        sell_indicators jsonb,
        sell_time timestamp,
        client_sell_time text,
        client_buy_time text
    );
    CREATE INDEX ON trades(symbol);
    CREATE INDEX ON trades(algo_run_id);
    CREATE INDEX ON trades(is_win);
    CREATE TABLE IF NOT EXISTS new_trades (
        trade_id serial PRIMARY KEY,
        algo_run_id integer REFERENCES algo_run(algo_run_id),
        symbol text NOT NULL,
        operation trade_operation NOT NULL,
        qty integer NOT NULL check (qty > 0),
        price decimal (8, 2) NOT NULL,
        indicators jsonb NOT NULL,
        client_time text,
        tstamp timestamp DEFAULT current_timestamp
    );
    CREATE INDEX ON new_trades(symbol);
    CREATE INDEX ON new_trades(algo_run_id);
    ALTER TABLE new_trades ADD COLUMN stop_price decimal (8, 2);
    ALTER TABLE new_trades ADD COLUMN target_price decimal (8, 2);
    ALTER TYPE trade_operation ADD VALUE 'sell_short';
    ALTER TYPE trade_operation ADD VALUE 'buy_short';
    CREATE TABLE IF NOT EXISTS ticker_data (
        symbol text PRIMARY KEY,
        name text NOT NULL,
        description text NOT NULL,
        tags text[],
        similar_tickers text[],
        industry text,
        sector text,
        exchange text,
        short_ratio float,
        create_tstamp timestamp DEFAULT current_timestamp,
        modify_tstamp timestamp
    );
    CREATE INDEX ON ticker_data(sector);
    CREATE INDEX ON ticker_data(industry);
    CREATE INDEX ON ticker_data(tags);
    CREATE INDEX ON ticker_data(similar_tickers);
    ALTER TABLE algo_run ADD COLUMN batch_id text NOT NULL DEFAULT '';
    CREATE INDEX ON algo_run(batch_id);
    ALTER TABLE algo_run ADD COLUMN ref_algo_run integer REFERENCES algo_run(algo_run_id);
    ALTER TABLE new_trades ADD COLUMN expire_tstamp timestamp;
    CREATE TABLE IF NOT EXISTS trending_tickers (
        trending_id serial PRIMARY KEY,
        batch_id text NOT NULL,
        symbol text NOT NULL,
        create_tstamp timestamp DEFAULT current_timestamp
    );
    CREATE INDEX ON trending_tickers(batch_id);
    INSERT INTO trending_tickers (symbol, batch_id)
        SELECT distinct t.symbol, r.batch_id
        FROM new_trades as t, algo_run as r
        WHERE
            t.algo_run_id = r.algo_run_id AND
            batch_id != '';

    BEGIN
    alter table new_trades drop constraint "new_trades_qty_check";
    alter table new_trades add check (qty >= 0);
    COMMIT;

the latest schema file can be found in the `setup` folder in LiuAlgoTrader distribution,
it is recommended to always use the latest DB schema file,
which is backward compatible and executing the scripts will automatically
migrate the data to the latest version.

Data Providers
--------------
Algorithmic trading is only as good as the data feed it rely on.
Without an accurate, near-real-time data feed even the
best strategy will keep losing money.

Luckily, Alpaca is well integrated with `Polygon.io`_ for free.
A funded Alpaca account is granted an access to Polygon live data streaming,
which is mostly accurate. A non-funded account has access only to Polygon
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

<tbd add more>

Preparing your trades
---------------------
<tbd add more>
