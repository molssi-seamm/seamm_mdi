MODULE := seamm_mdi

.PHONY: help format lint install test coverage

help:
	@echo "format   - reformat with black"
	@echo "lint     - black --check + flake8"
	@echo "install  - (re)install into the active environment"
	@echo "test     - run the tests"

format:
	black $(MODULE) tests

lint:
	black --check $(MODULE) tests
	flake8 $(MODULE) tests

install:
	pip uninstall -y $(MODULE) 2>/dev/null || true
	pip install .

test:
	pytest tests/

coverage:
	pytest --cov=$(MODULE) tests/
