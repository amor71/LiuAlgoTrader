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

ALTER TABLE
    new_trades
ADD
    COLUMN stop_price decimal (8, 2);

ALTER TABLE
    new_trades
ADD
    COLUMN target_price decimal (8, 2);

ALTER TYPE trade_operation
ADD
    VALUE 'sell_short';

ALTER TYPE trade_operation
ADD
    VALUE 'buy_short';

CREATE TABLE IF NOT EXISTS ticker_data (
    symbol text PRIMARY KEY,
    name text NOT NULL,
    description text NOT NULL,
    tags text [ ],
    similar_tickers text [ ],
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

ALTER TABLE
    algo_run
ADD
    COLUMN batch_id text NOT NULL DEFAULT '';

CREATE INDEX ON algo_run(batch_id);

ALTER TABLE
    algo_run
ADD
    COLUMN ref_algo_run integer REFERENCES algo_run(algo_run_id);

ALTER TABLE
    new_trades
ADD
    COLUMN expire_tstamp timestamp;

CREATE TABLE IF NOT EXISTS trending_tickers (
    trending_id serial PRIMARY KEY,
    batch_id text NOT NULL,
    symbol text NOT NULL,
    create_tstamp timestamp DEFAULT current_timestamp
);

CREATE INDEX ON trending_tickers(batch_id);

INSERT INTO
    trending_tickers (symbol, batch_id)
SELECT
    distinct t.symbol,
    r.batch_id
FROM
    new_trades AS t,
    algo_run AS r
WHERE
    t.algo_run_id = r.algo_run_id
    AND batch_id != '';

BEGIN
;

alter TABLE
    new_trades DROP constraint "new_trades_qty_check";

alter TABLE
    new_trades
add
    check (qty != 0);

COMMIT;

CREATE TABLE IF NOT EXISTS stock_ohlc (
    symbol_id serial PRIMARY KEY,
    symbol text NOT NULL,
    symbol_date date NOT NULL,
    open float NOT NULL,
    high float NOT NULL,
    low float NOT NULL,
    close float NOT NULL,
    volume int NOT NULL,
    indicators JSONB,
    modify_tstamp timestamp,
    create_tstamp timestamp DEFAULT current_timestamp,
    UNIQUE(symbol, symbol_date)
);

CREATE INDEX ON stock_ohlc(symbol);

CREATE INDEX ON stock_ohlc(symbol_date);

CREATE TABLE IF NOT EXISTS gain_loss (
    gain_loss_id serial PRIMARY KEY,
    symbol text NOT NULL,
    algo_run_id integer NOT NULL REFERENCES algo_run(algo_run_id),
    gain_percentage decimal (5, 2) NOT NULL,
    gain_value decimal (8, 2) NOT NULL,
    tstamp timestamp DEFAULT current_timestamp,
    UNIQUE(symbol, algo_run_id)
);

CREATE INDEX ON gain_loss(symbol, algo_run_id);

CREATE INDEX ON algo_run(start_time);

CREATE INDEX ON new_trades(tstamp);

ALTER TABLE
    new_trades
ALTER COLUMN
    algo_run_id
SET
    NOT NULL;

CREATE TABLE IF NOT EXISTS trade_analysis (
    trade_analysis_id serial PRIMARY KEY,
    symbol text NOT NULL,
    algo_run_id integer NOT NULL REFERENCES algo_run(algo_run_id),
    start_tstamp timestamp with time zone NOT NULL,
    end_tstamp timestamp with time zone NOT NULL,
    gain_percentage decimal (5, 2) NOT NULL,
    gain_value decimal (8, 2) NOT NULL,
    r_units decimal(4, 2),
    tstamp timestamp with time zone DEFAULT current_timestamp,
    UNIQUE(symbol, algo_run_id, start_tstamp)
);

---------------
-- Portfolio --
---------------

alter TABLE
    new_trades DROP constraint "new_trades_qty_check";


CREATE TABLE IF NOT EXISTS keystore (
    keystore_id serial PRIMARY KEY,
    algo_name text NOT NULL,
    context text NOT NULL,
    key text NOT NULL,
    value text NOT NULL,
    tstamp timestamp with time zone DEFAULT current_timestamp,
    CONSTRAINT ukey UNIQUE (algo_name, key, context)
);

CREATE INDEX ON keystore(algo_name);

CREATE INDEX ON keystore(algo_name, key, context);

CREATE TABLE IF NOT EXISTS portfolio (
    portfolio_id text PRIMARY KEY,
    size int NOT NULL,
    stock_count int NOT NULL,
    parameters JSONB,
    expire_tstamp timestamp with time zone,
    tstamp timestamp with time zone DEFAULT current_timestamp
);


CREATE TABLE IF NOT EXISTS portfolio_batch_ids (
    assoc_id serial PRIMARY KEY,
    portfolio_id text NOT NULL REFERENCES portfolio(portfolio_id),
    batch_id text NOT NULL,
    UNIQUE(portfolio_id, batch_id)
);

CREATE INDEX ON portfolio_batch_ids(batch_id);

CREATE INDEX ON portfolio_batch_ids(portfolio_id);

--------------
-- Accounts --
--------------

CREATE TABLE IF NOT EXISTS accounts (
    account_id serial PRIMARY KEY,
    balance float NOT NULL DEFAULT 0.0,
    allow_negative bool NOT NULL DEFAULT FALSE,
    credit_line float NOT NULL DEFAULT 0. CHECK (credit_line > 0 or not allow_negative ),
    details JSONB,
    create_tstamp timestamp with time zone DEFAULT current_timestamp,
    modified_tstamp timestamp with time zone
);


CREATE TABLE IF NOT EXISTS account_transactions (
    transaction_id serial PRIMARY KEY,
    account_id SERIAL REFERENCES accounts(account_id),
    amount float NOT NULL,
    details JSONB,
    tstamp timestamp with time zone DEFAULT current_timestamp
);
ALTER TABLE account_transactions ADD COLUMN create_tstamp timestamp with time zone DEFAULT current_timestamp;

CREATE OR REPLACE FUNCTION update_balance() 
    RETURNS TRIGGER 
    LANGUAGE PLPGSQL 
    AS 
$$ 
DECLARE
    negative bool;
    b float;
    credit float;
BEGIN
    SELECT
        allow_negative,
        balance,
        credit_line
    FROM
        accounts
    WHERE
        account_id = NEW .account_id
    INTO negative, b, credit;
    
    UPDATE
        accounts
    SET
        balance = balance + NEW .amount,
        modified_tstamp = 'now()'
    WHERE
        account_id = NEW .account_id;

    RETURN NEW;

END;
$$;

CREATE 
    TRIGGER balance_update 
BEFORE 
    INSERT OR UPDATE
ON 
    account_transactions FOR EACH ROW EXECUTE PROCEDURE update_balance();


ALTER TABLE portfolio DROP COLUMN stock_count;
ALTER TABLE portfolio ADD COLUMN account_id int REFERENCES accounts(account_id);
CREATE INDEX IF NOT EXISTS portfolio_idx ON portfolio(account_id);


ALTER TABLE trending_tickers ADD COLUMN scanner_name text NOT NULL DEFAULT 'momentum';
CREATE INDEX  IF NOT EXISTS trending_tickers_scanner_idx ON trending_tickers (scanner_name);
CREATE INDEX IF NOT EXISTS  trending_tickers_tstamp_idx ON trending_tickers (create_tstamp);
ALTER TABLE  trending_tickers ALTER COLUMN create_tstamp TYPE timestamp with time zone;



CREATE TABLE IF NOT EXISTS optimizer_run (
    optimizer_run_id serial PRIMARY KEY,
    optimizer_session_id text NOT NULL,
    batch_id text NOT NULL,
    tstamp timestamp with time zone DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS  optimizer_run_idx ON optimizer_run(optimizer_session_id);


ALTER TABLE optimizer_run ADD COLUMN parameters text NOT NULL DEFAULT('');

alter table new_trades alter COLUMN qty type numeric(24,10) using cast(qty as numeric);

ALTER TABLE new_trades ADD COLUMN trade_fee NUMERIC(9,2) NOT NULL DEFAULT 0.0;

CREATE TYPE asset_type AS ENUM ('US_EQUITIES', 'CRYPTO');

ALTER TABLE portfolio ADD COLUMN assets asset_type NOT NULL DEFAULT 'US_EQUITIES';

ALTER TABLE portfolio ADD COLUMN external_account_id text;

ALTER TABLE portfolio ADD COLUMN broker text;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS trade_plan (
    trade_plan_id uuid DEFAULT uuid_generate_v4 (),
    portfolio_id text NOT NULL REFERENCES portfolio(portfolio_id),
    filename text NOT NULL,
    start_date date NOT NULL,
    strategy_name text NOT NULL,
    parameters JSONB,
    create_tstamp timestamp with time zone DEFAULT current_timestamp,
    modify_tstamp timestamp with time zone,
    expire_tstamp timestamp with time zone,
    PRIMARY KEY (trade_plan_id)
);

CREATE  FUNCTION update_modify_tstamp_action()
RETURNS TRIGGER AS $$
BEGIN
    NEW.modify_tstamp = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_trade_plan_modify_tstamp
    BEFORE UPDATE
    ON
        trade_plan
    FOR EACH ROW
EXECUTE PROCEDURE update_modify_tstamp_action();

CREATE TABLE IF NOT EXISTS trade_plan_execution_audit (
    execution_id serial PRIMARY KEY,
    trade_plan_id uuid REFERENCES trade_plan(trade_plan_id),
    details JSONB,
    started_on timestamp with time zone DEFAULT current_timestamp,
    ended_on timestamp with time zone DEFAULT current_timestamp
);

ALTER TABLE trade_plan DROP COLUMN filename;

alter table keystore drop column context;
alter table keystore drop column algo_name;
drop table keystore;

CREATE TABLE IF NOT EXISTS keystore (
    key text PRIMARY KEY,
    value text NOT NULL,
    tstamp timestamp with time zone DEFAULT current_timestamp
);

alter table portfolio_batch_ids drop CONSTRAINT "portfolio_batch_ids_portfolio_id_batch_id_key";
