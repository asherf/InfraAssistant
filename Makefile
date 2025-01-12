fmt:
	ruff check . --fix --select F401 --select I
	ruff format --line-length 120

lint:
	ruff check . --select F401 --select I --line-length 120

bootstrap:
	uv sync

run:
	PYTHONPATH=src:$PYTHONPATH uv run uvicorn assistant.run.main:app  --port 8080  --reload

shell:
	PYTHONPATH=src:$PYTHONPATH uv run ipython

test:
	PYTHONPATH=src:$PYTHONPATH uv run pytest --verbose