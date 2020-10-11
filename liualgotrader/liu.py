#!/usr/bin/env python
import os
import sys
import pygit2
import pathlib

from liualgotrader.common import config


def show_version():
    print(f"Liu Algo Trading Framework v{config.build_label}")


def show_usage():
    show_version()

    print()
    print(f"usgae: liu quickstart")
    print()


def quickstart():
    print(f"Welcome to Lig Algo Trading Framework v{config.build_label}!")
    print()
    print("This wizard will guide you through the setup process.")
    print()
    print("Step #1 - Alpaca.Markets credentials")
    print()
    print("To use Liu Algo Trading Framework you need a funded Alpaca Markets account,")
    print("do you already have a funded account [Y]/n:")
    i = input()
    have_funded = True if len(i) == 0 or (i == 'y' or i == 'Y' or i.lower() == 'yes') else False

    if not have_funded:
        print("For additional details `https://alpaca.markets/docs/about-us/`")
        return

    print("Liu Algo Trading Framework uses Polygon.io data for both LIVE and PAPER trading.")
    print()
    if not config.prod_api_key_id or not config.paper_api_secret:
        print("The Framework expects two environment variables to be set:")
        print("`APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` reflecting the funded")
        print("account's API key and secret respectively.")
        print("Please set the two environment and re-run the wizard.")
        return
    else:
        print("both `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY we found.")

    print()
    print("Step #2 - Database configuration:")
    print()
    print("Do you already have a PostgreSQL instance configured [N]/y:")
    i = input()
    already_have_db = True if len(i) > 0 and (i == 'y' or i == 'Y' or i.lower() == 'yes') else False

    if already_have_db:
        print("Follow the instructions at 'https://liualgotrader.readthedocs.io/en/latest/Installation%20&%20Setup.html#database-setup' to complete your database setup.")
    else:
        pwd = pathlib.Path().absolute()
        print(f"Select location for database files [{pwd}]:")
        db_location = input()
        db_location = pwd if not len(db_location) else db_location
        print("Select the database nane for keeping track of your trading [liu]:")
        db_name = input()
        db_name = 'liu' if not len(db_name) else db_name
        print("Select the database user-name [liu]:")
        user_name = input()
        user_name = 'liu' if not len(user_name) else user_name
        print("Select the database password [liu]:")
        password = input()
        password = 'liu' if not len(password) else password

if __name__ == "__main__":
    config.filename = os.path.basename(__file__)

    try:
        config.build_label = pygit2.Repository("../").describe(
            describe_strategy=pygit2.GIT_DESCRIBE_TAGS
        )
    except pygit2.GitError:
        import liualgotrader

        config.build_label = liualgotrader.__version__ if hasattr(liualgotrader, "__version__") else ""  # type: ignore

    if len(sys.argv) != 2:
        show_usage()
        exit(0)
    if sys.argv[1] == "quickstart":
        try:
            quickstart()
        except KeyboardInterrupt:
            print("Oops... ^C... exiting gracefully")
    else:
        show_usage()

    exit(0)