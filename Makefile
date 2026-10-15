# Real2Scenario — environment management
#
# Two environments run the same code, configured differently.
# Concepts: docs/current/environment-environments.md
#
#   dev   -> http://100.114.248.93:5173   your private visual check
#   prod  -> https://project-n3.hahuy.cloud  judges, behind the shared key
#
# Quick start:
#   make dev        start the dev environment
#   make prod       build the bundle and start the product environment
#   make status     what is running
#   make stop       stop everything

SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE_DEV  := docker compose -f compose.dev.yml
COMPOSE_PROD := docker compose -f compose.demo.yml
COMPOSE_PROD_RUN := $(COMPOSE_PROD) $(MAKE_ENV)

# Match the container user to the host user so bind-mounted files stay writable.
MAKE_ENV := R2S_UID=$(shell id -u) R2S_GID=$(shell id -g)

.PHONY: help dev dev-build dev-logs dev-down \
        prod prod-build-only prod-logs prod-down prod-rebuild \
        key status stop clean-volumes test \
        promote revert rollback-check

## ---------------------------------------------------------------- help

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

## ---------------------------------------------------------------- development

dev: ## Start the dev environment (Vite HMR, no auth, private network)
	$(COMPOSE_DEV) up -d
	@echo
	@echo "  Dev UI   http://100.114.248.93:5173"
	@echo "  Dev API  http://127.0.0.1:8001/api/health"

dev-build: ## Rebuild dev images after dependency or Dockerfile changes
	$(COMPOSE_DEV) up -d --build

dev-logs: ## Tail dev logs
	$(COMPOSE_DEV) logs -f

dev-down: ## Stop the dev environment
	$(COMPOSE_DEV) down

## ---------------------------------------------------------------- product

prod: ## Build the frontend bundle, then start the product environment
	@echo "==> Building the production bundle (judges never see a dev server)"
	cd frontend && npm run build
	@echo "==> Starting the product stack"
	$(COMPOSE_PROD_RUN) up -d --remove-orphans
	@echo
	@echo "  Product   https://project-n3.hahuy.cloud"
	@echo "  Key       ./ops/scripts/generate-demo-credentials.sh"
	@echo
	@echo "  Remember: 'make dev-down' before the contest. The dev stack serves"
	@echo "  the same app unauthenticated on 0.0.0.0:8001 and 0.0.0.0:5173."

prod-build-only: ## Rebuild the product images and bundle, then restart
	$(COMPOSE_PROD_RUN) up -d --build --remove-orphans

prod-logs: ## Tail product logs
	$(COMPOSE_PROD_RUN) logs -f

prod-down: ## Stop the product environment
	$(COMPOSE_PROD_RUN) down

prod-rebuild: ## Rebuild the bundle and recreate the product stack
	cd frontend && npm run build
	$(COMPOSE_PROD_RUN) up -d --build --force-recreate --remove-orphans

## ---------------------------------------------------------------- promotion

# READ THIS FIRST.
#
# There is no code promotion boundary today. Both stacks bind-mount the same
# host directory (.:/app) and the product api runs `uvicorn --reload`, so:
#
#   * Python / backend edits  -> live in product within ~1 second. Saving a file
#                               while working in dev changes production now.
#                               `make promote` does nothing for these.
#   * Frontend edits          -> NOT live. Product serves the frozen bundle in
#                               frontend/dist until the bundle is rebuilt.
#
# Only the frontend needs a promote step. That asymmetry is the whole story.
# See docs/current/environment-environments.md.

promote: ## Publish the current frontend bundle to the product environment
	@echo "==> Running the full suite first"
	$(MAKE) test
	@echo "==> Building and publishing the bundle"
	cd frontend && npm run build
	$(COMPOSE_PROD_RUN) up -d --remove-orphans
	@echo
	@echo "  Published. Verify: https://project-n3.hahuy.cloud"
	@echo "  Backend code was already live via the shared bind mount."

revert: ## Roll back to a known-good commit. Usage: make revert SHA=<commit>
	@test -n "$(SHA)" || { echo "usage: make revert SHA=<commit>"; exit 2; }
	@echo "==> Current HEAD: $$(git rev-parse --short HEAD)"
	@echo "==> Rolling back to: $(SHA)"
	@git rev-parse --verify $(SHA) >/dev/null 2>&1 || { echo "unknown commit: $(SHA)"; exit 1; }
	@echo "==> Frontend working tree is being reset to $(SHA)"
	@git checkout $(SHA) -- frontend/
	cd frontend && npm run build
	$(COMPOSE_PROD_RUN) up -d --remove-orphans
	@echo
	@echo "  Frontend rolled back to $(SHA)."
	@echo "  Backend was already reverted by the bind mount, but check"
	@echo "  'git status' — uncommitted backend edits are NOT affected."

rollback-check: ## Show what is currently published versus what is committed
	@echo "HEAD:          $$(git rev-parse --short HEAD)"
	@echo "working tree:  $$(git status --porcelain | wc -l) changed file(s)"
	@echo
	@echo "Backend is live from the working tree, not from a commit."
	@git status --porcelain -- src/ | sed 's/^/  /'
	@echo
	@echo "Frontend bundle in production:"
	@ls -la frontend/dist/assets/*.js 2>/dev/null | sed 's/^/  /' || echo "  (not built)"

## ---------------------------------------------------------------- operations

key: ## Generate or rotate the contest shared key and TLS certificate
	./ops/scripts/generate-demo-credentials.sh

status: ## Show what is running in both environments
	@echo "=== dev (project-n3) ==="
	@$(COMPOSE_DEV) ps --format '  {{.Name}}  {{.Status}}  {{.Ports}}' || true
	@echo "=== product (project-n3-prod) ==="
	@$(COMPOSE_PROD_RUN) ps --format '  {{.Name}}  {{.Status}}  {{.Ports}}' || true
	@echo
	@echo "=== host load ==="
	@uptime

stop: ## Stop both environments
	$(COMPOSE_DEV) down
	$(COMPOSE_PROD_RUN) down

test: ## Run the Python and frontend test suites
	PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
	cd frontend && npm test

clean-volumes: ## DANGER: delete product artifacts and the shared metadata index
	@echo "This deletes product scenarios, reports AND the 787 MB metadata index."
	@echo "The index will be rebuilt from 2.6 GB of nuScenes tables, taking minutes."
	@read -p "Type 'yes' to continue: " ok; [ "$$ok" = "yes" ] || exit 1
	-$(COMPOSE_PROD_RUN) down -v
	-docker volume rm r2s-metadata-cache
