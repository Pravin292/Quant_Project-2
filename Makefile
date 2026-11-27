.PHONY: install test lint typecheck fmt run web check check-web

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
	npm ci

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

web:
	npm run dev

check-web:
	npm run lint && npm run build && npm run typecheck

check: lint typecheck test
