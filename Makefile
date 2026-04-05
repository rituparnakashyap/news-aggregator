.PHONY: install test lint run validate

install:
	pip install -e ".[dev]"

test:
	pytest --cov=news_aggregator --cov-report=term-missing

lint:
	ruff check .
	mypy news_aggregator/

run:
	news-aggregator run --config config/default.yaml

validate:
	news-aggregator validate-config --config config/default.yaml
