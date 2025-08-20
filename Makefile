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
	$(PY) -m src.store_emails

psql:
	docker exec -it gmail_rule_parser_db psql -U $$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' gmail_rule_parser_db | awk -F= '/POSTGRES_USER/{print $$2; exit}') -d $$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' gmail_rule_parser_db | awk -F= '/POSTGRES_DB/{print $$2; exit}')

process_rules:
	$(PY) -m src.process_rules -r src/rules.json

reset-db:
	$(PY) -m src.reset_db

setup-db:
	$(PY) -m src.setup_db


