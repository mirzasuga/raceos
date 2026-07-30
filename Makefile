.PHONY: setup test test-cov lint fmt clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Install all dependencies
	uv sync --all-extras
	@echo "✅ Dependencies installed. Run 'make test' to verify."

test: ## Run unit tests
	uv run pytest tests/ -v --tb=short -m "not slow"

test-cov: ## Run tests with coverage report
	uv run pytest tests/ --cov=src/factory --cov-report=term-missing --cov-fail-under=80

test-all: ## Run all tests including slow/integration
	uv run pytest tests/ -v --tb=short

lint: ## Run linter and format checker
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

fmt: ## Auto-format code
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

clean: ## Remove build artifacts and caches
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned"

check: lint test ## Run lint + tests (CI equivalent)
