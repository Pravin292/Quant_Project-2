.PHONY: install test lint typecheck fmt run check

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check . && .venv/bin/black --check .

typecheck:
	.venv/bin/mypy src api scripts

fmt:
	.venv/bin/ruff check --fix . && .venv/bin/black .

run:
	.venv/bin/uvicorn api.index:app --reload

check: lint typecheck test
