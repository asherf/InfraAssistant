fmt:
	ruff check . --fix --select F401  # Remove unused imports
	ruff format

lint:
	ruff check .

bootstrap:
	uv sync

run:
	PYTHONPATH=src:$PYTHONPATH uv run uvicorn assistant.run.main:app  --port 8080  --reload

shell:
	PYTHONPATH=src:$PYTHONPATH uv run ipython
