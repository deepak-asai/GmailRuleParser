PYTHON?=python3
PIP?=./.venv/bin/pip
PY?=./.venv/bin/python

.PHONY: venv install up stop down logs run psql rules reset-db setup-db

venv:
	$(PYTHON) -m venv .venv
	./.venv/bin/pip install --upgrade pip

install: venv
	$(PIP) install -r requirements.txt

up:
	docker compose up -d db

stop:
	docker compose stop
	
down:
	docker compose down

logs:
	docker compose logs -f db

store_emails:
	$(PY) -m src.email_store_service

psql:
	docker exec -it gmail_rule_parser_db psql -U $$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' gmail_rule_parser_db | awk -F= '/POSTGRES_USER/{print $$2; exit}') -d $$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' gmail_rule_parser_db | awk -F= '/POSTGRES_DB/{print $$2; exit}')

process_rules:
	$(PY) -m src.rule_processor_service -r src/rules.json

reset:
	$(PY) -m src.scripts.reset_db

setup:
	$(PY) -m src.scripts.setup_db

test:
	./run_tests.sh

process_emails:
	$(PY) -m src.main

