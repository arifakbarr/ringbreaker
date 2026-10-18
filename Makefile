.PHONY: install test lint hero proof record verify-decisions deploy smoke clean ui-build

PYTHON ?= python
PIP ?= pip

install:
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON) -m pytest -q

lint:
	ruff check src tests
	mypy src/ringbreaker --ignore-missing-imports || true

hero:
	$(PYTHON) -m ringbreaker.harness.run_hero

baselines:
	$(PYTHON) -m ringbreaker.harness.baselines

proof:
	$(PYTHON) -m ringbreaker.harness.run_proof

record:
	$(PYTHON) -m ringbreaker.harness.record_demo

verify-decisions:
	$(PYTHON) -m ringbreaker.harness.verify_decisions

ui-build: record
	cd ui && npm ci && npm run build

deploy:
	bash deploy/deploy.sh

free-up:
	docker compose -f deploy/docker-compose.free.yml up --build

free-down:
	docker compose -f deploy/docker-compose.free.yml down

smoke:
	bash scripts/smoke.sh

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
