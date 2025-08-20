#!/bin/bash

# Run integration tests first (they use real database)
echo "1. Running PostgreSQL integration tests..."
python3 -m pytest tests/test_store_emails_postgres_integration.py -v

# Run unit tests (they use mocks)
echo ""
echo "2. Running unit tests..."
python3 -m pytest tests/test_gmail_api.py tests/test_process_rules.py tests/test_storage.py tests/test_store_emails.py -v

echo ""
echo "All tests completed!"
