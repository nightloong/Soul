.PHONY: install dev-api dev-web test lint build
install:
	python -m pip install -e ".[dev]"
	npm install
dev-api:
	python -m uvicorn personaforge.main:app --host 127.0.0.1 --port 8000 --reload
dev-web:
	npm run dev
test:
	pytest
	npm test
lint:
	ruff check .
	npm run lint
build:
	npm run build
