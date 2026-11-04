.PHONY: bootstrap dev dev-host stop lint test test-integration test-security test-e2e smoke contracts
bootstrap:
	python scripts/configure.py
	uv sync --frozen
	pnpm install --frozen-lockfile
	pnpm exec playwright install chromium --only-shell
	docker compose up -d --wait postgres minio temporal
	uv run alembic upgrade head
	uv run python -m foundry.bootstrap
dev:
	uv run python scripts/dev.py
dev-containers:
	docker compose up -d --build
dev-host:
	uv run python scripts/dev.py
stop:
	uv run python scripts/stop.py
	docker compose down
lint:
	uv run ruff check apps/api packages/sdk-python scripts tests
	uv run ruff format --check apps/api packages/sdk-python scripts tests
	pnpm typecheck
test:
	uv run pytest -q -m 'not integration and not security'
test-integration:
	uv run pytest -q -m integration
test-security:
	uv run pytest -q -m security
test-e2e:
	pnpm test:e2e
smoke:
	uv run python scripts/smoke.py
contracts:
	uv run python scripts/contracts.py
	pnpm generate:types
