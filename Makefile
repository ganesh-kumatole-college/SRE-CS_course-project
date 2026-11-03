PYTHON ?= python3

.PHONY: setup test lint format neo4j-up neo4j-down smoke-gds

setup:
	$(PYTHON) -m pip install -r requirements.txt -e .

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests scripts

format:
	$(PYTHON) -m black src tests scripts

neo4j-up:
	docker compose up -d

neo4j-down:
	docker compose down

smoke-gds:
	$(PYTHON) scripts/smoke_gds.py
