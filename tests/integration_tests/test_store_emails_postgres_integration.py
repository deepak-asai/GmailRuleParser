import pytest
import os
import time
from unittest.mock import Mock, patch
from datetime import datetime, timezone
import base64
from sqlalchemy import text

from src.email_store_service import EmailStoreService
from src.db_service import DatabaseService
from src.models import Email, Base


class TestEmailStoreServicePostgresIntegration:
    """Integration tests for EmailStoreService with real PostgreSQL database"""
    
    def setup_method(self):
        """Set up test fixtures before each test method"""
        # Test database configuration
        self.test_db_name = "gmail_rule_parser_test"
        self.test_db_user = "gmail_rule_parser"
        self.test_db_password = "postgres"
        self.test_db_host = "localhost"
        self.test_db_port = 5432
        
        # Create test database URL
        self.database_url = f"postgresql+psycopg://{self.test_db_user}:{self.test_db_password}@{self.test_db_host}:{self.test_db_port}/{self.test_db_name}"
        
        # Clear singleton instances to ensure fresh database service
        if hasattr(DatabaseService, '__wrapped__'):
            DatabaseService.__wrapped__.instances = {}
        
        # Create database service with test database
        self.mock_settings_patcher = patch('src.db_service.get_settings')
        self.mock_settings = self.mock_settings_patcher.start()
        self.mock_settings.return_value.database_url = self.database_url
        self.db_service = DatabaseService()
        
        # Drop all tables and recreate schema
        Base.metadata.drop_all(bind=self.db_service.engine)
        Base.metadata.create_all(bind=self.db_service.engine)
        
        # Create mock Gmail API service
        self.mock_gmail_service = Mock()
        
        # Create EmailStoreService with mocked Gmail API and real database
        self.email_store_service = EmailStoreService(
            gmail_api_service=self.mock_gmail_service,
            db_service=self.db_service
        )
    
    def teardown_method(self):
        """Clean up test fixtures after each test method"""
        # Stop the settings patch
        self.mock_settings_patcher.stop()
        
        # Close database connections
        if hasattr(self.db_service, 'engine'):
            self.db_service.engine.dispose()
        
        # Clear singleton instances
        if hasattr(DatabaseService, '__wrapped__'):
            DatabaseService.__wrapped__.instances = {}
    
    def create_mock_gmail_message(self, message_id: str, **kwargs) -> dict:
        """Helper method to create mock Gmail message data"""
        default_data = {
            "gmail_message_id": message_id,
            "thread_id": f"thread_{message_id}",
            "history_id": 12345,
            "subject": f"Test Subject {message_id}",
            "from_address": f"sender_{message_id}@example.com",
            "to_address": "recipient@example.com",
            "label_ids": ["INBOX", "UNREAD"],
            "received_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        }
        default_data.update(kwargs)
        return default_data
    
    def test_store_single_page_postgres_integration(self):
        """Test storing a single page of emails with real PostgreSQL database"""
        # Mock Gmail API responses
        mock_message_ids = ["msg1", "msg2", "msg3"]
        self.mock_gmail_service.list_message_ids_in_inbox.return_value = (mock_message_ids, None)
        
        # Mock full message data
        mock_messages = {
            "msg1": self.create_mock_gmail_message("msg1", subject="Important Email 1"),
            "msg2": self.create_mock_gmail_message("msg2", subject="Important Email 2"),
            "msg3": self.create_mock_gmail_message("msg3", subject="Important Email 3")
        }
        self.mock_gmail_service.get_messages_for_rules_batch.return_value = mock_messages
        
        # Execute the service
        inserted_count = self.email_store_service.store_single_page(max_results=50)
        
        # Verify Gmail API was called correctly
        self.mock_gmail_service.list_message_ids_in_inbox.assert_called_once_with(None, max_results=50)
        self.mock_gmail_service.get_messages_for_rules_batch.assert_called_once_with(mock_message_ids)
        
        # Verify database contains the emails
        with self.db_service.get_session() as session:
            emails = session.query(Email).all()
            
            assert len(emails) == 3
            assert inserted_count == 3
            
            # Verify email data
            email_ids = [email.gmail_message_id for email in emails]
            assert "msg1" in email_ids
            assert "msg2" in email_ids
            assert "msg3" in email_ids
            
            # Verify specific email data
            msg1_email = session.query(Email).filter_by(gmail_message_id="msg1").first()
            assert msg1_email.subject == "Important Email 1"
            assert msg1_email.from_address == "sender_msg1@example.com"
            assert msg1_email.to_address == "recipient@example.com"
    
    def test_fetch_and_store_emails_postgres_integration(self):
        """Test fetching and storing multiple pages of emails with PostgreSQL"""
        # Mock Gmail API responses for multiple pages
        self.mock_gmail_service.list_message_ids_in_inbox.side_effect = [
            (["msg1", "msg2"], "next_page_token"),  # First page
            (["msg3", "msg4"], None)                 # Second page (last)
        ]
        
        # Mock full message data for both pages
        mock_messages_page1 = {
            "msg1": self.create_mock_gmail_message("msg1", subject="Page 1 Email 1"),
            "msg2": self.create_mock_gmail_message("msg2", subject="Page 1 Email 2")
        }
        mock_messages_page2 = {
            "msg3": self.create_mock_gmail_message("msg3", subject="Page 2 Email 1"),
            "msg4": self.create_mock_gmail_message("msg4", subject="Page 2 Email 2")
        }
        
        self.mock_gmail_service.get_messages_for_rules_batch.side_effect = [
            mock_messages_page1,
            mock_messages_page2
        ]
        
        # Execute the service
        total_inserted = self.email_store_service.fetch_and_store_emails(max_pages=2, max_results_per_page=2)
        
        # Verify Gmail API was called correctly
        assert self.mock_gmail_service.list_message_ids_in_inbox.call_count == 2
        assert self.mock_gmail_service.get_messages_for_rules_batch.call_count == 2
        
        # Verify database contains all emails
        with self.db_service.get_session() as session:
            emails = session.query(Email).all()
            assert len(emails) == 4
            assert total_inserted == 4
            
            # Verify all message IDs are present
            email_ids = [email.gmail_message_id for email in emails]
            assert "msg1" in email_ids
            assert "msg2" in email_ids
            assert "msg3" in email_ids
            assert "msg4" in email_ids
    
    def test_duplicate_handling_postgres_integration(self):
        """Test that duplicate emails are handled correctly with PostgreSQL upsert"""
        # First, insert some emails
        mock_message_ids = ["msg1", "msg2"]
        self.mock_gmail_service.list_message_ids_in_inbox.return_value = (mock_message_ids, None)
        
        mock_messages = {
            "msg1": self.create_mock_gmail_message("msg1", subject="Original Subject"),
            "msg2": self.create_mock_gmail_message("msg2", subject="Another Email")
        }
        self.mock_gmail_service.get_messages_for_rules_batch.return_value = mock_messages
        
        # Insert first batch
        inserted_count1 = self.email_store_service.store_single_page(max_results=50)
        assert inserted_count1 == 2
        
        # Now try to insert the same emails again (should be skipped by PostgreSQL ON CONFLICT DO NOTHING)
        inserted_count2 = self.email_store_service.store_single_page(max_results=50)
        assert inserted_count2 == 0  # No new emails inserted
        
        # Verify database still has only 2 emails
        with self.db_service.get_session() as session:
            emails = session.query(Email).all()
            assert len(emails) == 2
    
    def test_empty_response_handling_postgres_integration(self):
        """Test handling of empty Gmail API responses with PostgreSQL"""
        # Mock empty response
        self.mock_gmail_service.list_message_ids_in_inbox.return_value = ([], None)
        self.mock_gmail_service.get_messages_for_rules_batch.return_value = {}
        
        # Execute the service
        inserted_count = self.email_store_service.store_single_page(max_results=50)
        
        # Verify no emails were inserted
        assert inserted_count == 0
        
        # Verify database is empty
        with self.db_service.get_session() as session:
            emails = session.query(Email).all()
            assert len(emails) == 0
    
    def test_large_batch_handling_postgres_integration(self):
        """Test handling of large batches of emails with PostgreSQL"""
        # Create a large batch of mock messages
        large_batch_size = 100
        mock_message_ids = [f"msg{i}" for i in range(large_batch_size)]
        self.mock_gmail_service.list_message_ids_in_inbox.return_value = (mock_message_ids, None)
        
        # Create mock messages for the large batch
        mock_messages = {}
        for i in range(large_batch_size):
            mock_messages[f"msg{i}"] = self.create_mock_gmail_message(
                f"msg{i}", 
                subject=f"Large Batch Email {i}"
            )
        self.mock_gmail_service.get_messages_for_rules_batch.return_value = mock_messages
        
        # Execute the service
        inserted_count = self.email_store_service.store_single_page(max_results=large_batch_size)
        
        # Verify all emails were inserted
        assert inserted_count == large_batch_size
        
        # Verify database contains all emails
        with self.db_service.get_session() as session:
            emails = session.query(Email).all()
            assert len(emails) == large_batch_size
            
            # Verify a few random emails
            sample_emails = session.query(Email).limit(5).all()
            for email in sample_emails:
                assert email.gmail_message_id.startswith("msg")
                assert email.subject.startswith("Large Batch Email")
    
    def test_error_handling_postgres_integration(self):
        """Test error handling when Gmail API fails with PostgreSQL"""
        # Mock Gmail API to raise an exception
        self.mock_gmail_service.list_message_ids_in_inbox.side_effect = Exception("Gmail API Error")
        
        # Execute the service and expect it to raise the exception
        with pytest.raises(Exception, match="Gmail API Error"):
            self.email_store_service.store_single_page(max_results=50)
        
        # Verify database is empty (no partial data)
        with self.db_service.get_session() as session:
            emails = session.query(Email).all()
            assert len(emails) == 0
    
    def test_database_constraints_postgres_integration(self):
        """Test that database constraints are properly enforced with PostgreSQL"""
        # Insert an email with required fields
        mock_message_ids = ["msg1"]
        self.mock_gmail_service.list_message_ids_in_inbox.return_value = (mock_message_ids, None)
        
        # Create message with minimal required data
        mock_messages = {
            "msg1": {
                "gmail_message_id": "msg1",
                "from_address": "sender@example.com",
                "to_address": "recipient@example.com",
                "created_at": datetime.now(timezone.utc)
            }
        }
        self.mock_gmail_service.get_messages_for_rules_batch.return_value = mock_messages
        
        # This should work (has required fields)
        inserted_count = self.email_store_service.store_single_page(max_results=50)
        assert inserted_count == 1
        
        # Verify the email was stored with default values for optional fields
        with self.db_service.get_session() as session:
            email = session.query(Email).filter_by(gmail_message_id="msg1").first()
            assert email.from_address == "sender@example.com"
            assert email.to_address == "recipient@example.com"
            assert email.subject is None  # Optional field
    
    def test_postgresql_upsert_performance(self):
        """Test PostgreSQL upsert performance with batch operations"""
        # Create a medium-sized batch
        batch_size = 50
        mock_message_ids = [f"msg{i}" for i in range(batch_size)]
        self.mock_gmail_service.list_message_ids_in_inbox.return_value = (mock_message_ids, None)
        
        # Create mock messages
        mock_messages = {}
        for i in range(batch_size):
            mock_messages[f"msg{i}"] = self.create_mock_gmail_message(
                f"msg{i}", 
                subject=f"Performance Test Email {i}"
            )
        self.mock_gmail_service.get_messages_for_rules_batch.return_value = mock_messages
        
        # Measure insertion time
        start_time = time.time()
        inserted_count = self.email_store_service.store_single_page(max_results=batch_size)
        end_time = time.time()
        
        # Verify all emails were inserted
        assert inserted_count == batch_size
        
        # Verify performance (should be reasonably fast)
        insertion_time = end_time - start_time
        assert insertion_time < 5.0  # Should complete within 5 seconds
        
        # Verify database contains all emails
        with self.db_service.get_session() as session:
            emails = session.query(Email).all()
            assert len(emails) == batch_size
