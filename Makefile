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
	printf "__travis_commit__ = \"${GIT_COMMIT}\"\n__time__ = \"${DATE}\"\n__travis_job_number__ = \"0\"\n__travis_job_url__ = \"\"\n" > ${APP_VERSION_FILE}

.PHONY: test
test:
	./scripts/run_tests.sh

.PHONY: babel-test
babel-test:
	make babel
	pybabel extract -F babel.cfg -k _l -o /tmp/messages.po . && po2csv /tmp/messages.po /tmp/messages.csv
	rm /tmp/messages.po
	python scripts/babel_tests.py /tmp/messages.csv
	rm /tmp/messages.csv

.PHONY: babel
babel: 
	csv2po app/translations/csv/en.csv app/translations/en/LC_MESSAGES/messages.po
	csv2po app/translations/csv/fr.csv app/translations/fr/LC_MESSAGES/messages.po
	pybabel compile -d app/translations

.PHONY: freeze-requirements
freeze-requirements:
	rm -rf venv-freeze
	virtualenv -p python3 venv-freeze
	$$(pwd)/venv-freeze/bin/pip install -r requirements-app.txt
	echo '# pyup: ignore file' > requirements.txt
	echo '# This file is autogenerated. Do not edit it manually.' >> requirements.txt
	cat requirements-app.txt >> requirements.txt
	echo '' >> requirements.txt
	$$(pwd)/venv-freeze/bin/pip freeze -r <(sed '/^--/d' requirements-app.txt) | sed -n '/The following requirements were added by pip freeze/,$$p' >> requirements.txt
	rm -rf venv-freeze

.PHONY: test-requirements
test-requirements:
	@diff requirements-app.txt requirements.txt | grep '<' \
	    && { echo "requirements.txt doesn't match requirements-app.txt."; \
	         echo "Run 'make freeze-requirements' to update."; exit 1; } \
|| { echo "requirements.txt is up to date"; exit 0; }

.PHONY: coverage
coverage: venv ## Create coverage report
	. venv/bin/activate && coveralls