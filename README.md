# Latch

Latch is in Milestone 1.1: engineering foundation only.

## Requirements

- Python 3.13
- uv
- Terraform

## Development

```sh
uv sync --dev
uv run uvicorn latch.main:app --reload
```

## Validation

```sh
uv run ruff check
uv run mypy src
uv run pytest
terraform -chdir=infrastructure/terraform validate
```
