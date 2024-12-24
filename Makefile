fmt:
	ruff check . --fix

lint:
	ruff check .

bootstrap:
	uv sync

run:
	uv run uvicorn src.main:app  --port 8080
