.PHONY: up down logs migrate backend frontend test lint

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f backend frontend

migrate:
	cd backend && alembic upgrade head

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev -- --host 0.0.0.0

test:
	cd backend && pytest

lint:
	cd backend && ruff check app tests
