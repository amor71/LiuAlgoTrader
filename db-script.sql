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
    end_time timestamp
);


CREATE TABLE IF NOT EXISTS trades (
    trade_id serial PRIMARY KEY,
    transaction_id integer NOT NULL,
    symbol text NOT NULL,
    op trade_operation NOT NULL,
    qty integer NOT NULL check (qty > 0),
    price decimal (8, 2) NOT NULL,
    indicators jsonb NOT NULL,
    fill_time   timestamp DEFAULT current_timestamp,
    algo_run_id integer REFERENCES algo_run(algo_run_id)
);
CREATE INDEX ON trades(transaction_id);
CREATE INDEX ON trades(symbol);
CREATE INDEX ON trades(algo_run_id);
