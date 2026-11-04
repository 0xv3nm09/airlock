.PHONY: dev check test bench

dev:      ## API with reload, dummy mode
	uvicorn app.main:app --reload --port 8000

check:    ## what CI runs
	ruff check app tests && pytest -q

test:
	pytest -q

bench:    ## seeded benchmark in dummy mode
	python -m app.eval.benchmark eval_cases/cases.yaml
