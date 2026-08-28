.PHONY: lint format format-check typecheck test check-all

lint:
	poetry run ruff check app/

format:
	poetry run ruff format app/

format-check:
	poetry run ruff format --check app/

typecheck:
	poetry run pyright

test:
	poetry run pytest

check-all: lint format-check typecheck test