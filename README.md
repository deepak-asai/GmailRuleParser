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

#### Docker Database Setup

The project uses Docker only for the PostgreSQL database. The Python application runs locally.

1. Copy env

```bash
cp env.example .env
```

2. Start PostgreSQL database

```bash
docker compose up -d db
```

3. Create venv and install deps (same as local setup)

```bash
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
```

4. Run the application locally

```bash
./.venv/bin/python -m src.main
```

#### Docker Commands

```bash
# Start PostgreSQL database
docker compose up -d db

# View database logs
docker compose logs -f db

# Stop database
docker compose down

# Access PostgreSQL
docker compose exec db psql -U gmail_rule_parser -d gmail_rule_parser

# Reset database (drop and recreate)
docker compose exec db psql -U gmail_rule_parser -d gmail_rule_parser -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

### Makefile shortcuts

```bash
# Local development
make install     # venv + deps
make up          # start db
make down        # stop all
make run         # run main
make psql        # psql into container
make test        # run all tests

# Docker database
make docker-up   # start postgres database
make docker-down # stop postgres database
make docker-logs # view database logs
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

### Environment Configuration

#### Local Development

For local development, the application connects to the PostgreSQL database running in Docker.

#### Database Configuration

The application connects to PostgreSQL running in Docker. Ensure your `.env` file has the correct database connection:

```bash
# Database configuration (PostgreSQL in Docker)
DATABASE_URL=postgresql+psycopg://gmail_rule_parser:postgres@localhost:5432/gmail_rule_parser

# Gmail API credentials
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8080
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
