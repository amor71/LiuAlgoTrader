Additional apps
===============


Optimizer
---------

The `optimizer` application is a tool for back-testing strategies, in parallel, while using different parameters. 
The optimizer helps selecting the best performing hyper-parameters for any strategy.

How-To
******

To use the `optimizer` application, a new section should be added to the `tradeplan.toml` file:

.. literalinclude:: ../../examples/optimizer/tradeplan.toml
  :language: python
  :linenos:

* Note the [optimizer] section added to the tradeplan.toml file,
* start_date & end_date specify the time-window for backtesting, 
* The `optimizer` always runs in daily time-scale,


Params and Hypers
*****************

The `optimizer` application supports two different 
types of configuration-space constructs: Parmeter and Hyper-Parameters.

Parameters are meta-instructions for generating configurations for strategies,
that are calculated per back-testing step. In contrast, Hyper-Parameters is a 
configuration space spanning a product of all possible values for each Hyper-Parameter. 

Usage
*****

To run the `optimizer` application, simply type: 

.. code-block:: bash

    optimizer

The application will read the `tradeplan.toml` file and spawn process for backtesting the different configurations. 

Model
*****
Each `optimizer` execution generates a UUID representing a unique exeuction identification. 
Each back-test will generate it's own `batch-id`. 
The relationship between the optimizer execution id, batch-ids and the hyper parameters configurations
is stored in the **OPTIMIZER_RUN** database table.

Analysis
********
A dedicated Jupter Notebook (see the `analysis` section) allows loading and comparing
performance of the different configurations.

Parallel execution
******************
Similarly to the `trader` application, the `optimizer` also supports multi-processing execution to optimize run times. By default the `optimizer` executes 4 process, however that may be changed by speciying the `--concurrency` parameter.


Portfolio
---------

The Portfolio app, uses Google Fire_ infrastructure for CLI development. 

.. _Fire: https://github.com/google/python-fire


The application provides means for creating portfolios, displaying current portfolio status in a neat table, displaying the cash account transactions, as well as a re-processing tool. 

Usage
*****

To see the diffent commands of the `portfolio` application, type: 

.. code-block:: bash

    portfolio --help


Create Portfolio
****************

To create a new portfolio, type:

.. code-block:: bash

    portfolio create <portfolio cash amount> <credit line>

For example, running the below creates a new portfolio, with a cash account of $10,000 and a credit line of $1,000.

.. code-block:: bash

    portfolio create 10000 1000


Re-processing
*************

The cash account is updated with every trade. Normally, there will not be a need to re-calculate the cash requests from the account. In some cases, however, where manual intervension is required, it may be helpful to re-caculate the cash transaction.

**WARNING**: This operation is not reversible ! 

To create a recalculate portfolio, type:

.. code-block:: bash

    portfolio recalc <portfolio-id> 


