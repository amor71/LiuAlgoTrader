#!/bin/bash
set -e

echo "Generate Coverage Report"
coverage run -m pytest --cov

echo "Convert report to XML"
coverage xml

echo "upload coverage report"
codecov -vt $CODECOV_TOKEN
