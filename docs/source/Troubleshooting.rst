Installation FAQ
================

Q
-

I'm trying to install Liu on Ubuntu and I get the error message:
.. code-block:: bash

**ImportError: cannot import name '_imaging' from 'PIL' (/usr/lib/python3/dist-packages/PIL/__init__.py)**

A
-
LiuAlgoTrader uses streamlit_ for some of it's visualizations. streamlit requires the Python PIL library. The imgaging library may not be installed out of the box and you will need to install it with (click here_ for additional details):
.. code-block:: bash

**sudo apt-get build-dep python-imaging**

**sudo apt-get install libjpeg62 libjpeg62-dev**

.. _streamlit:
    https://streamlit.io/

.. _here:
    https://askubuntu.com/questions/156484/how-do-i-install-python-imaging-library-pil


