PYTHON ?= ../.venv/bin/python
PIP ?= ../.venv/bin/pip
MANAGE := $(PYTHON) manage.py
PYTEST := $(PYTHON) -m pytest
PODMAN ?= podman
PG_CONTAINER ?= vitable-pg18
PG_IMAGE ?= docker.io/library/postgres:18
PG_PORT ?= 55432

ifneq (,$(wildcard .env))
include .env
export DEBUG ALLOWED_HOSTS CORS_ALLOW_ALL_ORIGINS
export POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD POSTGRES_HOST POSTGRES_PORT
export OPENROUTER_API_KEY
endif

.DEFAULT_GOAL := help


.PHONY: help install run dev shell check migrate makemigrations createsuperuser \
	test test-file test-k test-v test-fast lint format typecheck quality docker-up docker-down \
	pg-up pg-down pg-logs pg-psql pg-create-db

help:
	@echo "Backend commands"
	@echo ""
	@echo "  make install         Install backend dependencies"
	@echo "  make run             Run Django dev server on 0.0.0.0:8000"
	@echo "  make dev             Alias for run"
	@echo "  make shell           Open Django shell"
	@echo "  make check           Run Django system checks"
	@echo "  make migrate         Apply database migrations"
	@echo "  make makemigrations  Create migrations from model changes"
	@echo "  make createsuperuser Create Django superuser"
	@echo "  make test            Run all backend tests"
	@echo "  make test-fast       Run tests in quiet mode"
	@echo "  make test-v          Run tests with verbose output"
	@echo "  make lint            Run Ruff checks (imports, style, bugs, annotations)"
	@echo "  make format          Format backend Python files with Ruff"
	@echo "  make typecheck       Enforce runtime function annotation coverage"
	@echo "  make quality         Run lint + typecheck + tests"
	@echo "  make test-file FILE=chatbot/test_api_chat.py"
	@echo "  make test-k KWORD=appointment"
	@echo "  make docker-up       Start postgres/backend/frontend with docker-compose"
	@echo "  make docker-down     Stop docker-compose services"
	@echo "  make pg-up           Start Podman PostgreSQL 18 on port 55432"
	@echo "  make pg-create-db    Create POSTGRES_DB in Podman PostgreSQL if missing"
	@echo "  make pg-psql         Open psql shell to Podman PostgreSQL"
	@echo "  make pg-logs         Tail Podman PostgreSQL logs"
	@echo "  make pg-down         Stop and remove Podman PostgreSQL container"

install:
	$(PIP) install -r requirements.txt

run:
	$(MANAGE) runserver 0.0.0.0:8000

dev: run

shell:
	$(MANAGE) shell

check:
	$(MANAGE) check

migrate:
	$(MANAGE) migrate

makemigrations:
	$(MANAGE) makemigrations

createsuperuser:
	$(MANAGE) createsuperuser

test:
	$(PYTEST)

test-fast:
	$(PYTEST) -q

test-v:
	$(PYTEST) -vv

test-file:
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make test-file FILE=chatbot/test_api_chat.py"; \
		exit 1; \
	fi
	$(PYTEST) "$(FILE)"

test-k:
	@if [ -z "$(KWORD)" ]; then \
		echo "Usage: make test-k KWORD=appointment"; \
		exit 1; \
	fi
	$(PYTEST) -k "$(KWORD)"

lint:
	$(PYTHON) -m ruff check chatbot backend manage.py

format:
	$(PYTHON) -m ruff format chatbot backend manage.py

typecheck:
	$(PYTHON) scripts/check_runtime_annotations.py

quality: lint typecheck test-fast

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down

pg-up:
	@if $(PODMAN) ps -a --format '{{.Names}}' | grep -qx '$(PG_CONTAINER)'; then \
		$(PODMAN) start $(PG_CONTAINER); \
	else \
		$(PODMAN) run -d --name $(PG_CONTAINER) \
			-e POSTGRES_USER=$(POSTGRES_USER) \
			-e POSTGRES_PASSWORD=$(POSTGRES_PASSWORD) \
			-e POSTGRES_DB=$(POSTGRES_DB) \
			-p $(PG_PORT):5432 \
			$(PG_IMAGE); \
	fi

pg-create-db:
	@PGPASSWORD="$(POSTGRES_PASSWORD)" psql -h "$(POSTGRES_HOST)" -p "$(POSTGRES_PORT)" -U "$(POSTGRES_USER)" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='$(POSTGRES_DB)'" | grep -q 1 || \
	PGPASSWORD="$(POSTGRES_PASSWORD)" psql -h "$(POSTGRES_HOST)" -p "$(POSTGRES_PORT)" -U "$(POSTGRES_USER)" -d postgres -c "CREATE DATABASE $(POSTGRES_DB);"

pg-psql:
	PGPASSWORD="$(POSTGRES_PASSWORD)" psql -h "$(POSTGRES_HOST)" -p "$(POSTGRES_PORT)" -U "$(POSTGRES_USER)" -d "$(POSTGRES_DB)"

pg-logs:
	$(PODMAN) logs -f $(PG_CONTAINER)

pg-down:
	-$(PODMAN) stop $(PG_CONTAINER)
	-$(PODMAN) rm $(PG_CONTAINER)
