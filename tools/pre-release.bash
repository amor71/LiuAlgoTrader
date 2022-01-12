#!/bin/bash
set -e

echo "Generate Coverage Report"
coverage run -m pytest

echo "Convert report to XML"
<<<<<<< HEAD
coverage xml 

echo "upload coverage report"
codecov -vt $CODECOV_TOKEN


=======
coverage XML

echo "upload coverage report"
codecov -vt $CODECOV_TOKEN
>>>>>>> master
