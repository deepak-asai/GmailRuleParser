## GmailRuleParser

Python project scaffold using venv locally and Postgres via Docker.

### Setup

1. Copy env

```bash
cp env.example .env
```

2. Create venv and install deps

```bash
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
```

3. Start Postgres

```bash
docker compose up -d db
```

4. Smoke test

```bash
./.venv/bin/python -m src.main
```

### Makefile shortcuts

```bash
make install     # venv + deps
make up          # start db
make down        # stop all
make run         # run main
make psql        # psql into container
make test        # run all tests
```

### Testing

Run all tests in the correct order to avoid mock interference:

```bash
./run_tests.sh
```

Or run tests individually:

```bash
# Integration tests (require PostgreSQL)
python3 -m pytest tests/test_store_emails_postgres_integration.py -v

# Unit tests
python3 -m pytest tests/test_gmail_api.py tests/test_process_rules.py tests/test_storage.py tests/test_store_emails.py -v
```

### Rules engine

Create a rules JSON file like `rules.json`:

```json
{
  "predicate": "Any",
  "rules": [
    {
      "predicate": "All",
      "conditions": [
        { "field": "From", "predicate": "Contains", "value": "@example.com" },
        { "field": "Subject", "predicate": "Contains", "value": "invoice" }
      ],
      "actions": { "mark": "read", "move": "Invoices" }
    }
  ]
}
```

Run the processor:

```bash
./.venv/bin/python -m gmail_rule_parser.process_rules rules.json --max 100
```
