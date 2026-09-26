PYTHON=venv/bin/python3.9
CONTAINER_ENGINE?=$(shell if command -v podman >/dev/null 2>&1; then echo podman; elif command -v docker >/dev/null 2>&1; then echo docker; fi)
IMAGE_NAME?=queuer:latest
SERVICE_NAME?=question-queuer
DATA_DIR?=$(CURDIR)/data
CONTAINER_VOLUME?=$(DATA_DIR):/bot/data$(if $(filter podman,$(CONTAINER_ENGINE)),:Z,)
HOST_UID?=$(shell id -u)
HOST_GID?=$(shell id -g)

.PHONY: venv install dev run test test-verbose check docker-build docker-up docker-down docker-logs clean

venv:
	$(PYTHON) -m venv venv && source venv/bin/activate
install:
	$(PYTHON) -m pip install -e .

dev:
	$(PYTHON) -m pip install -e .[dev]

run:
	PYTHONPATH=src $(PYTHON) -m queuer

test:
	PYTHONPATH=src $(PYTHON) -m pytest

test-verbose:
	PYTHONPATH=src $(PYTHON) -m pytest -v

check:
	$(PYTHON) -m compileall src

docker-build:
	$(CONTAINER_ENGINE) build -t $(IMAGE_NAME) -f Dockerfile .

docker-up:
	mkdir -p $(DATA_DIR)
	-$(CONTAINER_ENGINE) rm -f $(SERVICE_NAME)
	$(CONTAINER_ENGINE) run -d \
		--name $(SERVICE_NAME) \
		--restart unless-stopped \
		$(if $(filter podman,$(CONTAINER_ENGINE)),--userns keep-id,) \
		--user $(HOST_UID):$(HOST_GID) \
		--env-file .env \
		-v $(CONTAINER_VOLUME) \
		$(IMAGE_NAME)

docker-down:
	-$(CONTAINER_ENGINE) rm -f $(SERVICE_NAME)

docker-logs:
	$(CONTAINER_ENGINE) logs -f $(SERVICE_NAME)

clean:
	rm -rf __pycache__ src/__pycache__ src/queuer/__pycache__