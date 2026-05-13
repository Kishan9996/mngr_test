PYTHON := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
VENV   := .venv
PY     := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

.PHONY: install dev seed seed-all test lint clean reset

# ── Virtual environment ────────────────────────────────────────────────────────

# Stamp file: only reinstalls when requirements.txt changes
$(VENV)/.installed: requirements.txt
	@echo "→ Creating virtual environment…"
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements.txt
	@touch $(VENV)/.installed
	@echo "✓ Dependencies installed"

install: $(VENV)/.installed

# ── Development ────────────────────────────────────────────────────────────────

dev: install
	$(PY) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# ── Seeding ────────────────────────────────────────────────────────────────────

seed: install
	$(PY) seed.py \
		--org-name "MNGR Demo" \
		--data-dir ../data_extraction_task/ai_data_extraction_chatbot_technical_task_sample_data \
		--admin-email admin@mngr.com \
		--admin-password changeme123

seed-all: install
	$(PY) seed.py \
		--org-name "MNGR Demo" \
		--data-dir ../data_extraction_task/ai_data_extraction_chatbot_technical_task_sample_data \
		--admin-email admin@mngr.com \
		--admin-password changeme123 \
		--seed-demo-org2
	@echo "✓ Seeded MNGR Demo (admin@mngr.com / changeme123)"
	@echo "✓ Seeded Acme Retail (admin@acme-retail.com / acme123456)"

# ── Quality ────────────────────────────────────────────────────────────────────

test: install
	$(PYTEST) tests/ -v --tb=short

lint: install
	$(VENV)/bin/ruff check app/ seed.py || true

# ── Housekeeping ───────────────────────────────────────────────────────────────

clean:
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Cleaned (.venv removed, DB and .env kept)"

reset: clean
	rm -f *.db
	@echo "✓ Reset complete (fresh DB on next 'make dev')"
