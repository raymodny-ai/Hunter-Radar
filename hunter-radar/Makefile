# 本地开发用 Makefile
.PHONY: up down logs psql redis-cli web migrate seed test lint fmt

up:
	cd infra && docker compose up -d
	@echo "Waiting for services to be ready..."
	@timeout /t 10 /nobreak >nul

down:
	cd infra && docker compose down

logs:
	cd infra && docker compose logs -f

psql:
	cd infra && docker compose exec postgres psql -U hunter -d hunter_radar

redis-cli:
	cd infra && docker compose exec redis redis-cli

web:
	cd infra && docker compose exec airflow-webserver airflow webserver

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python -m etl.symbol_seed

test:
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check .

fmt:
	cd backend && uv run ruff check --fix . && uv run ruff format .
