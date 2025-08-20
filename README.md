### Setup

1. Download and install Docker Desktop

2. Clone the repository

```bash
git clone https://github.com/deepak-asai/GmailRuleParser.git
cd GmailRuleParser
```

3. Install virtual environment and dependencies

```bash
make venv
make install
```

4. Copy environment file and set appropriate DB values

```bash
cp env.example .env
```

5. Set up Google API credentials

Follow these steps to set up Google API access:

- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create a new project
- Navigate to **APIs & Services** in the left sidebar
- Enable the **Gmail API** service
- Go to **OAuth consent screen** and configure it
- Create **OAuth Client ID** credentials and choose **Desktop application** as the application type
- Download the credentials file and save it as `credentials.json` at root folder


6. Start PostgreSQL database

```bash
make up
```

7. Create `rules.json` in root directory:

```json
[{
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
}]
```

8. Run the application. When starting the app for 1st time it will open your browser for authentication. Once completed, a `token.json` file will be created.

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
make test
```

### Environment Configuration

#### Local Development

For local development, the application connects to the PostgreSQL database running in Docker.

### Rules engine


Run the processor:

```bash
./.venv/bin/python -m src.rule_processor_service rules.json --max 100
```
