.PHONY: install test build dev-backend dev-frontend fixture

install:
	python3 -m venv .venv
	.venv/bin/pip install -e '.[dev]'
	cd frontend && npm install

test:
	.venv/bin/pytest -q
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build

dev-backend:
	.venv/bin/uvicorn flight_dashboard.main:app --host 0.0.0.0 --port 8080 --reload

dev-frontend:
	cd frontend && npm run dev

fixture:
	python3 tools/fixture_sender.py --hz 20

