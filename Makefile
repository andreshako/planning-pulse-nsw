.PHONY: setup ingest build docs check

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
DBT := ../$(VENV)/bin/dbt

setup:
	test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

ingest:
	@test -x $(PYTHON) || (echo "ERROR: $(VENV) not found. Run: make setup" && exit 1)
	$(PYTHON) scripts/ingest_da_sample.py

build:
	@test -x $(PYTHON) || (echo "ERROR: $(VENV) not found. Run: make setup" && exit 1)
	@test -f dbt_planning_pulse/profiles.yml || (echo "ERROR: dbt_planning_pulse/profiles.yml not found. Run: cp dbt_planning_pulse/profiles.yml.example dbt_planning_pulse/profiles.yml" && exit 1)
	@test -f data/planning_pulse.duckdb || (echo "ERROR: data/planning_pulse.duckdb not found. Run: make ingest" && exit 1)
	cd dbt_planning_pulse && DBT_PROFILES_DIR=. $(DBT) build

docs:
	@test -x $(PYTHON) || (echo "ERROR: $(VENV) not found. Run: make setup" && exit 1)
	@test -f dbt_planning_pulse/profiles.yml || (echo "ERROR: dbt_planning_pulse/profiles.yml not found. Run: cp dbt_planning_pulse/profiles.yml.example dbt_planning_pulse/profiles.yml" && exit 1)
	@test -f data/planning_pulse.duckdb || (echo "ERROR: data/planning_pulse.duckdb not found. Run: make ingest" && exit 1)
	cd dbt_planning_pulse && DBT_PROFILES_DIR=. $(DBT) docs generate

check:
	@test -x $(PYTHON) || (echo "ERROR: $(VENV) not found. Run: make setup" && exit 1)
	@test -f dbt_planning_pulse/profiles.yml || (echo "ERROR: dbt_planning_pulse/profiles.yml not found. Run: cp dbt_planning_pulse/profiles.yml.example dbt_planning_pulse/profiles.yml" && exit 1)
	cd dbt_planning_pulse && DBT_PROFILES_DIR=. $(DBT) parse
