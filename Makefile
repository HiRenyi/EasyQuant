.PHONY: setup run dev test lint clean frontend

PYTHON := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
VENV := .venv
BIN := $(VENV)/bin

setup:
	@echo "==> Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"
	@if [ ! -f .env ]; then cp .env.example .env && echo "==> Created .env from template (edit as needed)"; fi
	@echo ""
	@echo "Setup complete! Run: make run"

run:
	$(BIN)/python -m quantgpt --transport http

dev:
	$(BIN)/python -m quantgpt --transport http --port 8003

test:
	$(BIN)/pytest tests/ -x -q

lint:
	$(BIN)/ruff check quantgpt/ tests/
	$(BIN)/pyright quantgpt/

frontend:
	cd frontend && npm ci && npm run build

clean:
	rm -rf $(VENV) *.egg-info __pycache__ quantgpt.db
