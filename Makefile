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

# Build provenance passed into the product image and reported by /api/health.
# Without it the image records nothing about which commit it came from, so the
# running product cannot be traced back to a commit without diffing source out
# of the container. Overridable so a deploy from a different tree is explicit
# rather than silently mislabelled.
PROJECT_N3_BUILD_COMMIT ?= $(shell git rev-parse HEAD 2>/dev/null || echo unknown)
PROJECT_N3_BUILD_COMMIT_TIME ?= $(shell git log -1 --format=%cI 2>/dev/null || echo unknown)
PROJECT_N3_BUILD_DIRTY ?= $(shell test -n "$$(git status --porcelain -- src frontend Dockerfile.prod pyproject.toml README.md 2>/dev/null)" && echo true || echo false)
MAKE_ENV := PROJECT_N3_BUILD_COMMIT=$(PROJECT_N3_BUILD_COMMIT) PROJECT_N3_BUILD_COMMIT_TIME=$(PROJECT_N3_BUILD_COMMIT_TIME) PROJECT_N3_BUILD_DIRTY=$(PROJECT_N3_BUILD_DIRTY)
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
	@$(MAKE) --no-print-directory prod-check-clean
	@echo "==> Starting the product stack"
	$(COMPOSE_PROD_RUN) up -d --remove-orphans
	@echo
	@echo "  Product   https://project-n3.hahuy.cloud"
	@echo "  Key       ./ops/scripts/generate-demo-credentials.sh"
	@echo
	@echo "  Remember: 'make dev-down' before the contest. The dev stack serves"
	@echo "  the same app unauthenticated on 0.0.0.0:8001 and 0.0.0.0:5173."

# The product image bakes in the repository instead of bind-mounting it, so the
# served code is whatever was committed at build time. Refuse to publish a
# half-finished working tree: an uncommitted edit in the product stack is
# invisible in git and cannot be reproduced or rolled back.
prod-check-clean:
	@dirty=$$(git status --porcelain -- . ':!log.txt' ':!frontend/wasm-esmini/a4_probe.mjs' ':!cpp-wasm-network.txt'); \
	if [ -n "$$dirty" ]; then \
		echo "==> Refusing to publish product from a dirty working tree:"; \
		echo "$$dirty" | sed 's/^/    /'; \
		echo ""; \
		echo "  Commit or stash first, then redeploy. The product image serves the"; \
		echo "  committed tree; see docs/current/environment-environments.md."; \
		exit 1; \
	fi

prod-build-only: ## Rebuild the product images and bundle, then restart
	@$(MAKE) --no-print-directory prod-check-clean
	$(COMPOSE_PROD_RUN) up -d --build --remove-orphans

prod-logs: ## Tail product logs
	$(COMPOSE_PROD_RUN) logs -f

prod-down: ## Stop the product environment
	$(COMPOSE_PROD_RUN) down

prod-rebuild: ## Rebuild the image from the committed tree and recreate the stack
	@$(MAKE) --no-print-directory prod-check-clean
	$(COMPOSE_PROD_RUN) up -d --build --force-recreate --remove-orphans

## ---------------------------------------------------------------- promotion

# The product image bakes in the repository instead of bind-mounting it, so
# there is now a real promotion boundary:
#
#   * Python and frontend source edits -> NOT live in product. They land when
#     the image is rebuilt from the committed tree.
#
# `promote` is therefore a full rebuild of the product image, which also
# recompiles the frontend bundle inside the image. There is no longer an
# asymmetry between backend and frontend.
# See docs/current/environment-environments.md.

promote: ## Publish the committed tree to the product environment
	@$(MAKE) --no-print-directory prod-check-clean
	@echo "==> Running the full suite first"
	$(MAKE) test
	@echo "==> Rebuilding and publishing the product image"
	$(COMPOSE_PROD_RUN) up -d --build --force-recreate --remove-orphans
	@echo
	@echo "  Published. Verify: https://project-n3.hahuy.cloud"
	@echo "  Backend and frontend both came from $$(git rev-parse --short HEAD)."

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
