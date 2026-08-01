format:
	uv run ruff format src/ tests/

typecheck:
	uv run ty check src/

lint:
	uv run ruff check --fix src/ tests/

test-cov:
	uv run pytest --cov=src --cov-report=term-missing -m "not integration"

pre-commit:
	uv run pre-commit run --all-files --config ../.pre-commit-config.yaml

quality:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/
	uv run ty check src/
	uv run pytest --cov=src --cov-report=term-missing -m "not integration"
