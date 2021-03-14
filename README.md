# LiuAlgoTrader
[![Build Status](https://travis-ci.org/amor71/LiuAlgoTrader.svg?branch=master)](https://travis-ci.org/amor71/LiuAlgoTrader)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/liualgotrader)
[![Python 3](https://pyup.io/repos/github/amor71/LiuAlgoTrader/python-3-shield.svg)](https://pyup.io/repos/github/amor71/LiuAlgoTrader/)
[![Updates](https://pyup.io/repos/github/amor71/LiuAlgoTrader/shield.svg)](https://pyup.io/repos/github/amor71/LiuAlgoTrader/)
[![Documentation Status](https://readthedocs.org/projects/liualgotrader/badge/?version=latest)](https://liualgotrader.readthedocs.io/en/latest/?badge=latest)
[![Tested with Hypothesis](https://img.shields.io/badge/hypothesis-tested-brightgreen.svg)](https://hypothesis.readthedocs.io/)
[![Gitter](https://badges.gitter.im/LiuAlgoTrader/community.svg)](https://gitter.im/LiuAlgoTrader/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

## Introduction

**LiuAlgoTrader** is a scalable, multi-process ML-ready framework
for effective algorithmic trading. The framework simplify development, testing,
deployment, analysis and training algo trading strategies. The framework **automatically analyzes** trading sessions, and the analysis may be used to train predictive models.  

LiuAlgoTrader can run on a laptop and 
*hedge-on-the-go*, or run on a multi-core hosted Linux server 
and it will automatically optimize for best performance for either. 

LiuAlgoTrader uses Alpaca.Markets brokerage APIs for trading, and can use either Alpaca or Polygon.io for stocks' data. The framework is evolving to support additional brokers and data-providers.

## See LiuAlgoTrader in Action

LiuAlgoTrader comes equipped with powerful & user-friendly back-testing tool. 

[Watch a $4,000 Profit](https://youtu.be/rVwFCbHsbIY) using LiuAlgoTrader out-of-the-box tools.


## Quickstart

### Prerequisite

- Paper, and/or a funded account with [Alpaca Markets](https://alpaca.markets/docs/about-us/).
- Polygon.io subscription optional (`Starter` plan and above),
- Installed [Docker Engine](https://docs.docker.com/engine/install/) and [Docker Compose](https://docs.docker.com/compose/install/)

### Install & Configure

**Step 1**: 
To install LiuAlgoTrader just type: 

`pip install liualgotrader`
 
**Step 2**: To configure the frame work type:

`liu quickstart` 

and follow the installation wizard instructions. The wizard will walk you
through the configuration of environment variables, setup of a local 
dockerized PostgreSQL and pre-populate with test data. 
 

### Try the samples

LiuAlgoTrader `quickstart` wizard installs samples allowing a first-time experience of the framework. Follow the post-installation instructions, and try to back-test a specific day.   

Additional samples can we found in the [examples](examples) directory. 

## Machine Learning 

These features are still work in process:

* [Design & Planning](https://github.com/amor71/LiuAlgoTrader/blob/master/design/ml-concepts.ipynb),
* [LSTM sample](https://github.com/amor71/LiuAlgoTrader/blob/master/analysis/notebooks/LSTM.ipynb)  
  
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
email me at  amichay@sgeltd.com

## Contributors

Special thanks to the below individuals for their comments, reviews and suggestions:

- Shlomi Kushchi [shlomikushchi](https://github.com/shlomikushchi)
- Venkat Y [vinmestmant](https://github.com/vinmestmant)
- Chris [crowforc3](https://github.com/crawforc3)
- [TheSnoozer](https://github.com/TheSnoozer)









