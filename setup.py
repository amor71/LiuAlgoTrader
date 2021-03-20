import codecs
import os.path

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("liualgotrader/requirements/release.txt") as f:
    requirements = f.read().splitlines()


def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), "r") as fp:
        return fp.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


setuptools.setup(
    name="liualgotrader",
    version=get_version("liualgotrader/__init__.py"),
    author="amor71",
    author_email="amichay@sgeltd.com",
    description="a Pythonic all-batteries-included framework for effective algorithmic trading. The framework is intended to simplify development, testing, deployment and evaluating algo trading strategies.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/amor71/LiuAlgoTrader",
    license="MIT",
    install_requires=requirements,
    data_files=[("liualgotrader", ["liualgotrader/requirements/release.txt"])],
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    scripts=[
        "liualgotrader/trader",
        "liualgotrader/market_miner",
        "liualgotrader/backtester",
        "liualgotrader/liu",
    ],
)
