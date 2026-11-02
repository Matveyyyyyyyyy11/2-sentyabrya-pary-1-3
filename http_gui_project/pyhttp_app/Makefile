.PHONY: install run test integration lint clean

install:
	pip install -r requirements.txt

run:
	python -m src.main

test:
	pytest tests/ -v

integration:
	pytest tests/test_integration.py -v

lint:
	flake8 src/ tests/
	pylint src/

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache http_gui.log
