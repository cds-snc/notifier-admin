.DEFAULT_GOAL := help
SHELL := /bin/bash #bash | sh
DATE = $(shell date +%Y-%m-%dT%H:%M:%S)

PIP_ACCEL_CACHE ?= ${CURDIR}/cache/pip-accel
APP_VERSION_FILE = app/version.py

GIT_BRANCH ?= $(shell git symbolic-ref --short HEAD 2> /dev/null || echo "detached")
GIT_COMMIT ?= $(shell git rev-parse HEAD 2> /dev/null || echo "")


.PHONY: help
help:
	@cat $(MAKEFILE_LIST) | grep -E '^[a-zA-Z_-]+:.*?## .*$$' | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: generate-version-file
generate-version-file: ## Generates the app version file
	printf "__commit_sha__ = \"${GIT_COMMIT}\"\n__time__ = \"${DATE}\"\n" > ${APP_VERSION_FILE}

.PHONY: test
test:
	./scripts/run_tests.sh

.PHONY: babel-test
test-translations: babel
	poetry run pybabel extract -F babel.cfg -k _l -o /tmp/messages.po . && poetry run po2csv /tmp/messages.po /tmp/messages.csv
	rm /tmp/messages.po
	python scripts/test-translations.py /tmp/messages.csv
	rm /tmp/messages.csv

.PHONY: babel
babel:
	python scripts/generate_en_translations.py
	poetry run csv2po app/translations/csv/en.csv app/translations/en/LC_MESSAGES/messages.po
	poetry run csv2po app/translations/csv/fr.csv app/translations/fr/LC_MESSAGES/messages.po
	poetry run pybabel compile -d app/translations

.PHONY: search-csv
search-csv:
	python scripts/search_csv.py

.PHONY: freeze-requirements
freeze-requirements:
	poetry lock --no-update

.PHONY: test-requirements
test-requirements:
	poetry check --lock

.PHONY: coverage
coverage: venv ## Create coverage report
	. venv/bin/activate && coveralls

.PHONY: run-dev
run-dev:
	poetry run flask run -p 6012 --host=localhost

.PHONY: format
format:
	ruff check --select I --fix .
	ruff check
	ruff format .
	mypy ./
	npx prettier --write app/assets/javascripts app/assets/stylesheets tests_cypress/cypress/e2e

.PHONY: tailwind
tailwind:
	npm run tailwind