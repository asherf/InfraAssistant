fmt:
	ruff check . --fix --select F401 --select I
	ruff format

lint:
	ruff check . --select F401 --select I

bootstrap:
	uv sync

run:
	PYTHONPATH=src:$PYTHONPATH uv run uvicorn assistant.run.main:app  --port 8080  --reload

shell:
	PYTHONPATH=src:$PYTHONPATH uv run ipython
