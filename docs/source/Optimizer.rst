Optimizer
=========

The `optimizer` application is a tool for back-testing strategies, in parallel, while using different parameters. 
The optimizer helps selecting the best performing hyper-parameters for any strategy.

How-To
------

To use the `optimizer` application, a new section should be added to the `tradeplan.toml` file:

.. literalinclude:: ../../examples/optimizer/tradeplan.toml
  :language: python
  :linenos:

* Note the [optimizer] section added to the tradeplan.toml file,
* start_date & end_date specify the time-window for backtesting, 
* The `optimizer` always runs in daily time-scale,


Params and Hypers
-----------------

The `optimizer` application supports two different 
types of configuration-space constructs: Parmeter and Hyper-Parameters.

Parameters are meta-instructions for generating configurations for strategies,
that are calculated per back-testing step. In contrast, Hyper-Parameters is a 
configuration space spanning a product of all possible values for each Hyper-Parameter. 

Usage
-----

To run the `optimizer` application, simply type: 

.. code-block:: bash

    optimizer

The application will read the `tradeplan.toml` file and spawn process for backtesting the different configurations. 

Model
-----
Each `optimizer` execution generates a UUID representing a unique exeuction identification. 
Each back-test will generate it's own `batch-id`. 
The relationship between the optimizer execution id, batch-ids and the hyper parameters configurations
is stored in the **OPTIMIZER_RUN** database table.

Analysis
--------
A dedicated Jupter Notebook (see the `analysis` section) allows loading and comparing
performance of the different configurations.

Parallel execution
------------------
Similarly to the `trader` application, the `optimizer` also supports multi-processing execution to optimize run times. By default the `optimizer` executes 4 process, however that may be changed by speciying the `--concurrency` parameter.






