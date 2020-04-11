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