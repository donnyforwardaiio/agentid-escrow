.PHONY: dev test migrate seed install

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v --tb=short --cov=app --cov-report=term-missing

migrate:
	alembic upgrade head

seed:
	python app/seed.py

lint:
	ruff check app/
