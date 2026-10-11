.PHONY: setup doctor dev dev-mock e2e test bench migrate clean

migrate:
	@echo "Running database migrations..."
	cd backend && uv run alembic upgrade head


setup:
	@echo "Setting up Python environments..."
	cd backend && uv venv && uv sync
	cd demo-shop && uv venv && uv sync
	@echo "Installing frontend dependencies..."
	cd frontend && npm install
	@echo "Installing Playwright browsers..."
	cd backend && uv run playwright install chromium
	@echo "Setup complete!"

doctor:
	@echo "Checking QAgent environment & services..."
	cd backend && uv run python -m qagent.doctor

dev:
	@echo "Starting QAgent development servers..."
	@echo "1. Demo Shop -> http://localhost:8001"
	@echo "2. Backend API -> http://localhost:8000"
	@echo "3. Next.js Frontend -> http://localhost:3000"
	npx concurrently -k -n "demo,backend,frontend" -c "yellow,blue,green" \
		"cd demo-shop && uv run uvicorn main:app --port 8001 --reload" \
		"cd backend && uv run uvicorn qagent.api.main:app --port 8000 --reload" \
		"cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev"

dev-mock:
	@echo "Frontend only, on in-browser fixtures (no backend needed)..."
	cd frontend && npm run dev

e2e:
	@echo "Drive the running stack through the UI (start 'make dev' first)..."
	cd backend && uv run python ../scripts/e2e_ui.py Stub

test:
	@echo "Running backend test suite..."
	cd backend && uv run pytest -v

bench:
	@echo "Running decision benchmark (Jev latency, candidate scaling & cost)..."
	cd backend && uv run python -m qagent.bench

clean:
	rm -rf backend/.venv demo-shop/.venv frontend/node_modules frontend/.next runs/
