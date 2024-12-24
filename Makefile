fmt:
	ruff check . --fix

lint:
	ruff check .

bootstrap:
	uv sync

run:
	uv run src/main.py
