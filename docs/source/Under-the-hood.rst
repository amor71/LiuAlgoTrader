.. _`Understanding what's under the hood`:


Understanding what's under the hood
===================================

This section explain the inner working of LiuAlgoTrader. It may be used to developer who wish
query LiuAlgoTrader database directly, optimize the application
for their specific setup, or contributing to
the on-going development of LiuAlgoTrader.

Understanding the multiprocessing approach
------------------------------------------

Understanding the Data Model
----------------------------

The data-model, as represented in the database tables can
be used by the various strategies, as well as for analysis
and back-testing.

This section describes the database schema and usage patterns.

ticker_data
***********

The ticker_data table keeps basic data on traded stocks
which include the symbol name, company name & description
as well as industry & sector and similar symbols.

It is recommended to use the *market_miner* application
to periodically refresh the data.

The industry & sector data is informative for creating
a per sector / industry trend.