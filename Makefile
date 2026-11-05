.PHONY: bootstrap dev dev-host stop lint test test-integration test-security test-e2e smoke contracts
bootstrap:
	python scripts/configure.py
	CC=gcc CXX=g++ CMAKE_ARGS='-DGGML_OPENMP=OFF -DGGML_BLAS=OFF' CMAKE_BUILD_PARALLEL_LEVEL=2 uv sync --frozen $(if $(wildcard .local/models/manifest.json),--extra local-model,)
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
local-model:
	CC=gcc CXX=g++ CMAKE_ARGS='-DGGML_OPENMP=OFF -DGGML_BLAS=OFF' CMAKE_BUILD_PARALLEL_LEVEL=2 uv sync --frozen --extra local-model
	uv run --no-sync python scripts/setup_local_model.py
blender:
	uv run python scripts/setup_blender.py --env-output .local/blender.env
test-recovery:
	uv run python scripts/operational_checks.py restore
test-load:
	uv run python scripts/operational_checks.py load
scan-security:
	uv run python scripts/security_review.py
