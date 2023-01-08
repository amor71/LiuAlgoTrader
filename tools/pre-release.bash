#!/bin/bash
set -e

echo "Generate Coverage Report"
python3 -m pytest -s --cov --cov-report xml

echo "upload coverage report"
codecov -vt $CODECOV_TOKEN
