VENV    := .venv
PYTHON  := $(VENV)/bin/python3
PIP     := $(VENV)/bin/pip
UV      := $(VENV)/bin/uvicorn
PYTEST  := $(VENV)/bin/pytest

.PHONY: venv install run test lint clean reset

# ── Virtual environment ────────────────────────────────────────────────────────

# Stamp file: only rebuilds when requirements.txt changes
$(VENV)/.installed: requirements.txt
	@echo "→ Creating virtual environment…"
	python3 -m venv $(VENV)
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements.txt
	@touch $(VENV)/.installed
	@echo "✓ Dependencies installed"

venv: $(VENV)/.installed

# Friendly alias
install: venv

# ── Development tasks ──────────────────────────────────────────────────────────

run: venv
	$(UV) app.main:app --reload --host 0.0.0.0 --port 8000

test: venv
	$(PYTEST) tests/ -v --tb=short

lint: venv
	$(VENV)/bin/ruff check app/ tests/ || true

# ── Housekeeping ───────────────────────────────────────────────────────────────

# Remove only the venv (keeps .env and the database)
clean:
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Cleaned"

# Full reset: venv + database
reset: clean
	rm -f *.db
	@echo "✓ Reset complete"
