pytest_check:
	poetry run pytest

ruff_check:
	poetry run ruff check .

black_check:
	poetry run black --check .

mypy_check:
	poetry run mypy .

tomlsort_check:
	poetry run tomlsort pyproject.toml
