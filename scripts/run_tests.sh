#!/bin/bash
#
# Run project tests
#
# NOTE: This script expects to be run from the project root with
# ./scripts/run_tests.sh

set -o pipefail

function display_result {
  RESULT=$1
  EXIT_STATUS=$2
  TEST=$3

  if [ $RESULT -ne 0 ]; then
    echo -e "\033[31m$TEST failed\033[0m"
    exit $EXIT_STATUS
  else
    echo -e "\033[32m$TEST passed\033[0m"
  fi
}

poetry check
display_result $? 1 "Requirements check"

make babel

ruff check .
display_result $? 1 "Code style check"

ruff check --select I .
display_result $? 1 "Import order check"

ruff format --check .
display_result $? 1 "Code format check"

mypy ./
display_result $? 1 "Type check"

npx prettier --check app/assets/javascripts app/assets/stylesheets tests_cypress/cypress/e2e
display_result $? 1 "JS/CSS code style check"

npm test
display_result $? 1 "npm test"

## Code coverage
py.test -n auto --maxfail=1 tests/ --strict -p no:warnings
display_result $? 1 "Code coverage"
