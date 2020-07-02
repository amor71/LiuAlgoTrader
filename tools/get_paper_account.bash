#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

source $DIR/set_keys.bash

echo "ALPACA PAPER ACCOUNT DETAILS"
curl -X GET \
    -H "APCA-API-KEY-ID:"$ALPACA_PAPER_API_KEY\
    -H "APCA-API-SECRET-KEY:"$ALPACA_PAPER_API_SECRET\
    $ALPACA_PAPER_BASEURL/v2/account | json_pp

