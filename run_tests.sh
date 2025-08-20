#!/bin/bash

# Run integration tests first (they use real database)
echo "1. Running PostgreSQL integration tests..."
python3 -m pytest tests/integration_tests/test_store_emails_postgres_integration.py -v

# Run unit tests (they use mocks)
echo ""
echo "2. Running unit tests..."
python3 -m pytest tests/unit_tests/test_gmail_api_service.py tests/unit_tests/test_rule_processor_service.py tests/unit_tests/test_db_service.py tests/unit_tests/test_email_store_service.py -v

echo ""
echo "All tests completed!"
