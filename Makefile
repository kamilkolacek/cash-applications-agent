.PHONY: setup data run finalize approve evals test lint status clean

# Call tools from the project venv directly, so nothing needs activating first.
BIN := .venv/bin

setup:
	uv venv --allow-existing && uv pip install -e ".[dev]"

data:
	$(BIN)/python scripts/generate_data.py

run:
	$(BIN)/python scripts/run_cash_app.py

finalize:
	$(BIN)/python scripts/finalize_run.py

# Human step. Claude Code is denied permission to run this.
approve:
	@test -n "$(APPROVER)" || (echo 'Usage: make approve APPROVER="Your Name"'; exit 1)
	$(BIN)/python scripts/approve.py --approver "$(APPROVER)"

evals:
	$(BIN)/python scripts/run_evals.py

status:
	$(BIN)/python scripts/status.py --all

test:
	$(BIN)/pytest -q

lint:
	$(BIN)/ruff check src tests scripts .claude/hooks

clean:
	find outputs/runs -mindepth 1 -maxdepth 1 -exec rm -r {} +
