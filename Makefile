PYTHON=python3
COMPOSE=docker compose

.PHONY: venv install dev run check docker-build docker-up docker-down docker-logs clean

venv:
	$(PYTHON) -m venv venv
install:
	$(PYTHON) -m pip install -e .

dev:
	$(PYTHON) -m pip install -e .[dev]

run:
	$(PYTHON) -m queuer

check:
	$(PYTHON) -m compileall src

docker-build:
	$(COMPOSE) build

docker-up:
	$(COMPOSE) up -d

docker-down:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f question-queuer

clean:
	rm -rf __pycache__ src/__pycache__ src/queuer/__pycache__