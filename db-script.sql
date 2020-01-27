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
