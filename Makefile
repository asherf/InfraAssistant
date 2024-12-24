fmt:
	ruff check . --fix
	ruff format

lint:
	ruff check .

bootstrap:
	uv sync

run:
	PYTHONPATH=src:$PYTHONPATH uv run uvicorn assistant.run.main:app  --port 8080
