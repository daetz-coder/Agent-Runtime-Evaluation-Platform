# Agent Evaluation Platform — Developer Makefile
#
# Common tasks for Agent engineers working on this platform.

.PHONY: help install lint typecheck test golden check-ci

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dev dependencies
	pip install -e ".[dev]"

lint: ## Run ruff linter
	ruff check . --fix

typecheck: ## Run mypy type checker
	mypy .

test: ## Run all tests
	python -m pytest tests/ -v

test-fast: ## Run tests (fast, skip slow vector tests)
	python -m pytest tests/ -v --ignore=tests/test_vector_store.py --ignore=tests/test_vector_admin.py

test-cov: ## Run tests with coverage report
	python -m pytest tests/ --cov=app --cov-report=term-missing

golden: ## Run Golden Test Suite (validate evaluator regression)
	python -m app.benchmarks.golden.runner

golden-verbose: ## Run Golden Suite with detailed output
	python -m app.benchmarks.golden.runner --fail-fast

check-regression: ## Run regression check between two evaluations
	python -m app.benchmarks.run_ci_gate --regression-base $(BASE) --regression-head $(HEAD)

check-ci: ## Full CI gate: golden suite + regression check
	python -m app.benchmarks.run_ci_gate

db-upgrade: ## Run Alembic migrations
	alembic upgrade head

db-downgrade: ## Rollback last migration
	alembic downgrade -1

run: ## Start backend server
	python -m app.main

run-dev: ## Start backend with auto-reload
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
