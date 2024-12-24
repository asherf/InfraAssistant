fmt:
	ruff check . --fix
	ruff format

lint:
	ruff check .

bootstrap:
	uv sync

run:
	uv run uvicorn src.main:app  --port 8080
