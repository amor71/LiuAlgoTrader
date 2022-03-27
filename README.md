# LiuAlgoTrader
[![Upload Python Package](https://github.com/amor71/LiuAlgoTrader/actions/workflows/python-publish.yml/badge.svg)](https://github.com/amor71/LiuAlgoTrader/actions/workflows/python-publish.yml)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/liualgotrader)
[![Python 3](https://pyup.io/repos/github/amor71/LiuAlgoTrader/python-3-shield.svg)](https://pyup.io/repos/github/amor71/LiuAlgoTrader/)
[![Updates](https://pyup.io/repos/github/amor71/LiuAlgoTrader/shield.svg)](https://pyup.io/repos/github/amor71/LiuAlgoTrader/)
[![Documentation Status](https://readthedocs.org/projects/liualgotrader/badge/?version=latest)](https://liualgotrader.readthedocs.io/en/latest/?badge=latest)
[![Tested with Hypothesis](https://img.shields.io/badge/hypothesis-tested-brightgreen.svg)](https://hypothesis.readthedocs.io/)
[![Gitter](https://badges.gitter.im/LiuAlgoTrader/community.svg)](https://gitter.im/LiuAlgoTrader/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)
[![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)
[![codecov](https://codecov.io/gh/amor71/LiuAlgoTrader/branch/master/graph/badge.svg?token=RIDO1ODHNQ)](https://codecov.io/gh/amor71/LiuAlgoTrader)

## Introduction

**LiuAlgoTrader** is a scalable, multi-process ML-ready framework for effective algorithmic trading. The framework simplifies development, testing, deployment, analysis, and training algo trading strategies. The framework automatically analyzes trading sessions, hyper-parameters optimization, and the analysis may be used to train predictive models.  

The framework currently support trading and back-testing of US Equities, and Crypto strategies.

LiuAlgoTrader can run on a laptop and *hedge-on-the-go*, or run on a multi-core hosted Linux server and it will automatically optimize for best performance for either. LiuAlgoTrader is a full trading platform with a breath of tools to manage automated investment portfolios.

LiuAlgoTrader supports:
* [Alpaca.Markets](https://alpaca.markets/) APIs for trading, and data loading & streaming.
* [Gemini Crypto Exchange](https://www.gemini.com/) APIs for trading, data loading & streaming.
* [Polygon.io](https://polygon.io/) APIs for data-loading, and streaming.
* (**BETA**) [Tradier](https://tradier.com/) APIs for trading and data. 


## See LiuAlgoTrader in Action

LiuAlgoTrader comes equipped with powerful & user-friendly back-testing tool. 

- [Watch a $4,000 Daily Profit](https://youtu.be/rVwFCbHsbIY) using LiuAlgoTrader Framework for Day Trading.
- [Watch Trend-Following strategy beating SP-500](https://youtu.be/BhifqoJBn84) using LiuAlgoTrader out-of-the-box tools for Swing Trading,
- [Sample tear-sheet](https://amor71.github.io/LiuAlgoTrader/tearsheet.html) using LiuAlgoTrader sample Trend Follow strategy.
- [Make 30% trading pair volatility](https://amor71.github.io/LiuAlgoTrader/brandtreade_tearsheet.html) using LiuAlgoTrader.


## Quick-start

### Prerequisite

- Paper, and/or a funded account with [Alpaca Markets](https://alpaca.markets/docs/about-us/).
OR Polygon.io subscription optional (`Starter` plan and above),
- Installed [Docker Engine](https://docs.docker.com/engine/install/) and [Docker Compose](https://docs.docker.com/compose/install/)

### Install & Configure

**Step 1**: 
To install LiuAlgoTrader just type: 

`pip install liualgotrader`

Having issues installation? check out the [installation FAQ page](https://liualgotrader.readthedocs.io/en/latest/Troubleshooting.html)
 
**Step 2**: To configure the frame work type:

`liu quickstart` 

and follow the installation wizard instructions. The wizard will walk you
through the configuration of environment variables, setup of a local 
dockerized PostgreSQL and pre-populate with test data. 
 
**Note** for [WINDOWS](https://liualgotrader.readthedocs.io/en/latest/Troubleshooting.html#q-can-i-run-liu-on-windows) users
### Try the samples

LiuAlgoTrader `quickstart` wizard installs samples allowing a first-time experience of the framework. Follow the post-installation instructions, and try to back-test a specific day.   

Additional samples can we found in the [examples](examples) directory. 

## Tutorials

LiuAlgoTraders articles are published on [Medium](https://amor71.medium.com/):

* [Walk thru of setup and backtesting (2 parts)](https://amor71.medium.com/liualgotrader-part-i-3334a27edd4b)
* [How to use the optimizer app](https://amor71.medium.com/liu-optimizer-42b0d6805d77)
* [How to setup a Trading Platform](https://amor71.medium.com/how-to-setup-your-trading-platform-part-i-64ea8ea828bb)


## Back-testing

While Liu is first and foremost a trading platform, it comes equipped with full back-testing capabilities, providing command-line tool & jupyter notebook for analysis, and a browser-based UI covering both functionalities.
## Machine Learning 

These features are still work in process:

* [Design & Planning](https://github.com/amor71/LiuAlgoTrader/blob/master/design/ml-concepts.ipynb),
* [LSTM sample](https://github.com/amor71/LiuAlgoTrader/blob/master/analysis/notebooks/LSTM.ipynb)  
* Attention (Transformer) : WIP  

## Analysis & Analytics

The framework includes a wide ranges of analysis `Jupyter Notebooks`, as well as `streamlit` applications for analysis for both trading and back-testing sessions. To name a few of the visual analytical tools:
* tear-sheet analysis,
* gain&loss analysis,
* anchored-VWAPs, 
* indicators & distributions

## What's Next?

Read the [documentation](https://liualgotrader.readthedocs.io/en/latest/) and learn how to use LiuAlgoTrader to develop, deploy & testing money making strategies.

## Watch the Evolution

`LiuAlgoTrader` is an ever evolving platform, to glimpse the concepts, thoughts and ideas 
visit the [design](https://github.com/amor71/LiuAlgoTrader/tree/master/design) folder and feel free to comment. 

## Contributing

Would you like to help improve & evolve LiuAlgoTrader? 
Do you have a suggestion, comment, idea for improvement or 
a have a wish-list item? Please read our
[Contribution Document](https://github.com/amor71/LiuAlgoTrader/blob/master/CONTRIBUTING.md) or 
email me at  amor71@sgeltd.com

## Contributors

Special thanks to the below individuals for their comments, reviews and suggestions:

- [Jonathan Morland-Barrett](https://github.com/sigmantium)
- [Alex Lau](https://github.com/riven314)
- [Rokas Gegevicius](https://github.com/ksilo)
- Shlomi Kushchi [shlomikushchi](https://github.com/shlomikushchi)
- Venkat Y [vinmestmant](https://github.com/vinmestmant)
- Chris [crowforc3](https://github.com/crawforc3)
- [TheSnoozer](https://github.com/TheSnoozer)
- [Aditya Gupta](https://github.com/adi0x90)
