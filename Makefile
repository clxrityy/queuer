PYTHON=python3

.PHONY: install dev run check clean

install:
	$(PYTHON) -m pip install -e .

dev:
	$(PYTHON) -m pip install -e .[dev]

run:
	$(PYTHON) -m queuer

check:
	$(PYTHON) -m compileall src

clean:
	rm -rf __pycache__ src/__pycache__ src/queuer/__pycache__