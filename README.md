## GmailRuleParser

Python project scaffold using venv locally and Postgres via Docker.

### Setup

1. Download and install Docker Desktop

2. Clone the repository

```bash
git clone https://github.com/deepak-asai/GmailRuleParser.git
cd GmailRuleParser
```

3. Install virtual environment and dependencies

```bash
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
```

4. Copy environment file and set appropriate DB values

```bash
cp env.example .env
```

5. Set up Google API credentials

Follow these steps to set up Google API access:

   a. Go to [Google Cloud Console](https://console.cloud.google.com/)
   b. Create a new project
   c. Navigate to **APIs & Services** in the left sidebar
   d. Enable the **Gmail API** service
   e. Go to **OAuth consent screen** and configure it
   f. Create **OAuth Client ID** credentials and choose **Desktop application** as the application type
   g. Download the credentials file and save it as `credentials.json` at root folder


5. Start PostgreSQL database

```bash
make up
```

6. Run the application. When starting the app for 1st time it will open your browser for authentication. Once completed, a `token.json` file will be created.

```bash
make process_emails
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
make tests
```

Or run tests individually:

```bash
# Integration tests (require PostgreSQL)
python3 -m pytest tests/test_store_emails_postgres_integration.py -v

# Unit tests
python3 -m pytest tests/test_gmail_api_service.py tests/test_rule_processor_service.py tests/test_db_service.py tests/test_email_store_service.py -v
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
./.venv/bin/python -m src.rule_processor_service rules.json --max 100
```
