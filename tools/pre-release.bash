#!/bin/bash
set -e

echo "Generate Coverage Report"
coverage run -m pytest

echo "Convert report to XML"
coverage XML

echo "upload coverage report"
codecov -vt $CODECOV_TOKEN