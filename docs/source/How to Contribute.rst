Contributing
============
Would you like to help improve & evolve LiuAlgoTrader? 
Do you have a suggestion, comment, idea for improvement or 
a have a wish-list item? Please read our
Contribution Document_ or email me at amichay@sgeltd.com.

.. _Document: https://github.com/amor71/LiuAlgoTrader/blob/master/CONTRIBUTING.md

How to setup a development environment
--------------------------------------

Below is a step-by-step mini-guide for setting up a local development environment.
1. clone LiuAlgoTrader:

.. code-block:: bash

    git clone https://github.com/amor71/LiuAlgoTrader.git

This would create a folder `LiuAlgoTrader` with the platform code, pointing to the `master` branch.
2. create a `virtualenv`:

.. code-block:: bash
    
    python3 -m venv liuenv

This would create a folder `liuenv`.

3. activate the `virtualenv`:

.. code-block:: bash

    source liuenv/bin/activate

4. install the packages required for development:

.. code-block:: bash

    pip install -r LiuAlgoTrader/liualgotrader/requirements/dev.txt

This step would download and install the latest packages required for the development. Note that `master` is the latest development branch. It may not be the most stable version. The latest stable version could be pulled from the latest tagged version.

5. If you have not yet set up a local database:

.. code-block:: bash

    python LiuAlgoTrader/liualgotrader/liu quickstart

Follow these_ instructions on using the quickstart wizard (note that `step 1` should be omitted).

.. _these: https://liualgotrader.readthedocs.io/en/latest/Quickstart.html




Contributors
------------

Special thanks to the below individuals for their comments, reviews and suggestions:

- Jonathan Morland-Barrett sigmantium_

.. _sigmantium: https://github.com/sigmantium

- Alex Lau riven314_

.. _riven314: https://github.com/riven314

- Rokas Gegevicius ksilo_

.. _ksilo: https://github.com/ksilo

- Shlomi Kushchi shlomikushchi_

.. _shlomikushchi: https://github.com/shlomikushchi

- Venkat Y vinmestmant_

.. _vinmestmant: https://github.com/vinmestmant

- Chris crowforc3_

.. _crowforc3: https://github.com/crawforc3

- TheSnoozer_

.. _TheSnoozer: https://github.com/TheSnoozer

- Aditya Gupta adi0x90_

.. _adi0x90: https://github.com/adi0x90



