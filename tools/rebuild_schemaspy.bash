#!/bin/bash
set -e

echo "Rebuild Schemaspy website"
java -jar /Users/amichayoren/Downloads/schemaspy-6.1.0.jar -t pgsql11 -dp ~/Downloads/postgresql-42.3.1.jar -db tradedb -host localhost -port 5432 -s public -u momentum -p ELmHCN5bhqjpS9gCYe -o database