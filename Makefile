.PHONY: sync lint typecheck test terraform-validate validate run

sync:
	uv sync --dev

lint:
	uv run ruff check

typecheck:
	uv run mypy src

test:
	uv run pytest

terraform-validate:
	terraform -chdir=infrastructure/terraform init -backend=false
	terraform -chdir=infrastructure/terraform validate

validate: lint typecheck test terraform-validate

run:
	uv run uvicorn latch.main:app --reload
