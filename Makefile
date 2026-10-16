# Standard targets. CLAUDE.md, the Stop hook, and CI refer to these names.
.PHONY: setup lint typecheck test test-fast style numbers agent-check ci \
	load reconcile evals up down

PY ?= python3

setup:
	$(PY) -m pip install -e ".[dev]"
	npm --prefix web ci
	pre-commit install

lint:
	ruff check .
	ruff format --check .

typecheck:
	npm --prefix web run typecheck

test:
	pytest -q

test-fast:
	pytest -x -q -m "not slow"

style:
	$(PY) scripts/agent/check_style.py .

# Every figure in these documents must come from a generated report.
numbers:
	$(PY) scripts/agent/check_numbers.py docs/WRITEUP.md docs/RECONCILIATION.md --sources build/reports

load:
	$(PY) -m pipeline.load

reconcile:
	$(PY) -m pipeline.reconcile

evals:
	$(PY) -m evals.run $(if $(RECORD),--record)

up:
	docker compose up --build

down:
	docker compose down

# The fast checks the Stop hook runs before Claude may end a turn.
agent-check:
	ruff check .
	ruff format --check .
	pytest -x -q -m "not slow"
	npm --prefix web run typecheck
	$(PY) scripts/agent/check_style.py .

ci: lint typecheck test style
	$(PY) scripts/agent/check_tests.py --warn
