**[NEW] Crypto**
================

**Crypto trading is still in BETA and in active development**

Asset types
-----------

The framework supports two asset types: US_EQUITIES and CRYPTO. 

When creating a portfolio for Crypto trading, use the following:

.. code-block:: bash

   portfolio create <size in FIAT currency> <credit in FIAT currency> CRYPTO


Gemini Crypto Exchange
----------------------

Gemini_ is a leading Crypto Exchange that provides APIs for Crypto trading, 
including live data stream and limited histrocial data. 

.. _gemini: https://www.gemini.com/

1. To trade using Gemini, make sure to set the  environment variables:

.. code-block:: bash

    export DATA_CONNECTOR="gemini"
    export LIU_BROKER="gemini"
    export GEMINI_API_KEY=
    export GEMINI_API_SECRET=

2. During BETA phase  the framework support `sandbox` trading only. To open a Sanbox account and obtain your API keys press here_ .

.. _here: https://exchange.sandbox.gemini.com/signin

3. During BETA phase only `BTCUSD` (Bitcoin to USD) is supported.

4. Backtesting and trading reamins same.

5. During BETA analysis supports only `Jupyter Notebook`, `Streamlit` support will be added at a later stage.

6. When using the Notebook(s) make sure to specify gemini as the DATA_CONNECTOR

7. Keep in mind that Gemini historical data is limited for the last 3 months, also loading bar data from Gemini in quite limited and slower than US Equities. It is recommanded for Strategies to pre-load historical data before starting to trade. Real-time streaming update seems quite fast and updated. 

8. During BETA make sure to execute `limit` orders only. `market` orders are not supported, however the platform would try to execute limit order as `Maker` orders at minimal costs,

9. keep in mind that Crypto trading is not-free and transactions may have fees associated with them. The Platform take it into account and withdraws from the account the approrpiate fees as well as properly store trading costs.

If you find any issues, please do not hesitate to report an issue or reach-out on the on-line chat. 


Polygon Crypto Data
-------------------
Polygon has a good support for Crypto data. If you are using Polygon.io you should check which package you are using and if it support Crypto. Note that Polygon abbrevates "X." in the name of Crypto pairs - for example BTCUSD would be X.BTCUSD on Polygon. That may require small modifications if you decide to use Polygon w Gemini (or another exchange)



Alpaca Crypto
-------------

Alpaca has a new and interesting Crypto offering, support for it will be released in the future. 





