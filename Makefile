.PHONY: serve test test-unit

serve:
	source .venv/bin/activate && uvicorn api.main:app --reload --port 8000

test:
	@echo "NOTE: requires server running (make serve in another terminal)"
	source .venv/bin/activate && python -m pytest tests/test_api.py -v --tb=short

test-unit:
	source .venv/bin/activate && python -m pytest tests/test_unit.py -v
