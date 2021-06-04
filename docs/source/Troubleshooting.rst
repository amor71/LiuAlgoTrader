Installation FAQ
================

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

