.PHONY: install test lint typecheck run docker package

install:
	python -m pip install -e ".[dev]"

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q

lint:
	ruff check src tests

typecheck:
	mypy src

run:
	python -m flow_memory --json "Explore and report"

docker:
	docker compose up -d --build

package:
	cd .. && zip -r flow-memory.zip flow-memory -x "flow-memory/.pytest_cache/*" "flow-memory/**/__pycache__/*"
