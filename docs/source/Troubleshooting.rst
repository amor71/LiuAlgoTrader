Installation FAQ
================


Q : Can I Run Liu on Windows?
-----------------------------

I have a Windows-based environment. Can I use `LiuAlgoTrader`?
 
Answer
******
 
Yes. While `LiuAlgoTrader` is developed & tested on macOS and Linux (Debian), Liu can run on Windows with few minor adaptations.
 
**Database Prerequisites**
 
LiuAlgoTrader uses PostgreSQL as a database. Liu installation wizard installs and configures a local PostgreSQL
using docker-compose. Postgres official docker image is based on Linux, and to run it on Windows machines,
you need to make sure you can run Linux images on your Windows.
 
You will need to search online to allow Linux containers on your Windows machine; there are ample 
resources online. Note that depending on your Windows distribution, your hardware may be required to support Hyper-V.
 
To sum up, before installing Liu on your Windows, you need to make sure:
 
1. Docker engine is installed and configured,
2. Docker compose installed and configured,
3. Your environment supports Linux containers
 
**Trading Setup**
 
It is OK to use Windows to develop strategies, but it is recommended to use Linux once you're ready to
move past back-testing. It is also recommended for the `production` environment to use a
dedicated PostgreSQL setup (local, hosted, or managed) vs. running in the Dockerized background.
 
**Running Liu applications**
 
`pip install liualgotrader` installs 4 executables scripts (a.k.a applications): **liu**, **trader**, **backtester** and **optimizer**.
On Windows (unlike Linux), it is not possible to execute the application by typing its name. You need to type `py <path>\liu`.
Where <path> depends on your local setup.
 
For example, assuming you have Python 3.9.x installed on your Windows machine, use to below steps to
create a dedicated `virtual environment` for Liu:
 
 .. code-block:: bash

    py -m venv liu
    liu\Scripts\activate
    pip install liualgotrader
    py liu\Scripts\liu quickstart
    
Good Luck!
 



Q : How to install on Ubuntu?
-----------------------------

I would like to install `liu` on Ubuntu 20.10. Can you please list the steps I need to take?

Answer
******

**STEP 1** : Install docker engine (Skip if already installed and running)

.. code-block:: bash

    $ sudo apt update
    $ sudo apt install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common
    $ curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
    $ sudo add-apt-repository \ "deb [arch=amd64] https://download.docker.com/linux/ubuntu \ $(lsb_release -cs) stable"
    $ sudo apt-get update
    $ sudo apt install docker-ce -y
    $ sudo usermod -aG docker $USER

After successful completetion of the above steps, you should logout and login.

**STEP 2**: Install docker-compose (Skip if already installed and working)

.. code-block:: bash

    $ sudo curl -L "https://github.com/docker/compose/releases/download/1.28.4/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    $ sudo chmod +x /usr/local/bin/docker-compose

**STEP 3**: Install Python3.9 and basic tools

.. code-block:: bash

    $ sudo add-apt-repository ppa:deadsnakes/ppa
    $ sudo apt update
    $ sudo apt install python3.9
    $ sudo apt install python3-pip
    $ sudo apt install python3.9-venv

**STEP 4**: Install LiuAlgoTrader 

.. code-block:: bash

    $ python3.9 -m venv liu
    $ source liu//bin/activate
    (liu) $ mkdir liu ; cd liu
    (liu) $ pip install liualgotrader


**STEP 5**: Run installation wizard

    *make sre you have environment keys properly selected*

.. code-block:: bash    

    (liu) $ liu quickstart

