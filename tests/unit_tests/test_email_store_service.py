import pytest
from unittest.mock import Mock, patch
from typing import Dict, List

from src.email_store_service import EmailStoreService, MAX_PAGES_TO_PROCESS, MAX_RESULTS_PER_PAGE


class TestEmailStoreService:
    """Test cases for EmailStoreService class"""
    
    def setup_method(self):
        """Set up test fixtures before each test method"""
        self.mock_gmail_service = Mock()
        self.mock_db_service = Mock()
        self.service = EmailStoreService(
            gmail_api_service=self.mock_gmail_service,
            db_service=self.mock_db_service
        )
    
    def test_init_with_services(self):
        """Test initialization with provided services"""
        service = EmailStoreService(
            gmail_api_service=self.mock_gmail_service,
            db_service=self.mock_db_service
        )
        
        assert service.gmail_api_service == self.mock_gmail_service
        assert service.db_service == self.mock_db_service
    
    @patch('src.email_store_service.GmailApiService')
    @patch('src.email_store_service.DatabaseService')
    def test_init_without_services(self, mock_db_class, mock_gmail_class):
        """Test initialization without provided services"""
        mock_gmail_instance = Mock()
        mock_db_instance = Mock()
        mock_gmail_class.return_value = mock_gmail_instance
        mock_db_class.return_value = mock_db_instance
        
        service = EmailStoreService()
        
        assert service.gmail_api_service == mock_gmail_instance
        assert service.db_service == mock_db_instance
        mock_gmail_class.assert_called_once()
        mock_db_class.assert_called_once()
    
    def test_fetch_and_store_emails_single_page(self):
        """Test fetching and storing emails with single page"""
        # Mock data
        message_ids = ["msg1", "msg2", "msg3"]
        email_data = {
            "msg1": {"gmail_message_id": "msg1", "subject": "Test 1"},
            "msg2": {"gmail_message_id": "msg2", "subject": "Test 2"},
            "msg3": {"gmail_message_id": "msg3", "subject": "Test 3"}
        }
        
        # Mock Gmail API responses
        self.mock_gmail_service.list_message_ids_in_inbox.return_value = (message_ids, None)
        self.mock_gmail_service.get_messages_for_rules_batch.return_value = email_data
        
        # Mock database response
        self.mock_db_service.upsert_emails.return_value = 3
        
        # Execute
        result = self.service.fetch_and_store_emails(max_pages=1)
        
        # Assertions
        assert result == 3
        self.mock_gmail_service.list_message_ids_in_inbox.assert_called_once_with(
            None, max_results=MAX_RESULTS_PER_PAGE
        )
        self.mock_gmail_service.get_messages_for_rules_batch.assert_called_once_with(message_ids)
        # Check that upsert_emails was called with the correct data
        self.mock_db_service.upsert_emails.assert_called_once()
        call_args = self.mock_db_service.upsert_emails.call_args[0][0]
        assert list(call_args) == list(email_data.values())
    
    def test_fetch_and_store_emails_multiple_pages(self):
        """Test fetching and storing emails with multiple pages"""
        # Mock data for first page
        message_ids_1 = ["msg1", "msg2"]
        email_data_1 = {
            "msg1": {"gmail_message_id": "msg1", "subject": "Test 1"},
            "msg2": {"gmail_message_id": "msg2", "subject": "Test 2"}
        }
        
        # Mock data for second page
        message_ids_2 = ["msg3", "msg4"]
        email_data_2 = {
            "msg3": {"gmail_message_id": "msg3", "subject": "Test 3"},
            "msg4": {"gmail_message_id": "msg4", "subject": "Test 4"}
        }
        
        # Mock Gmail API responses
        self.mock_gmail_service.list_message_ids_in_inbox.side_effect = [
            (message_ids_1, "page_token_1"),
            (message_ids_2, None)
        ]
        self.mock_gmail_service.get_messages_for_rules_batch.side_effect = [
            email_data_1,
            email_data_2
        ]
        
        # Mock database responses
        self.mock_db_service.upsert_emails.side_effect = [2, 2]
        
        # Execute
        result = self.service.fetch_and_store_emails(max_pages=2)
        
        # Assertions
        assert result == 4
        assert self.mock_gmail_service.list_message_ids_in_inbox.call_count == 2
        assert self.mock_gmail_service.get_messages_for_rules_batch.call_count == 2
        assert self.mock_db_service.upsert_emails.call_count == 2
        
        # Check first page call
        self.mock_gmail_service.list_message_ids_in_inbox.assert_any_call(
            None, max_results=MAX_RESULTS_PER_PAGE
        )
        # Check second page call
        self.mock_gmail_service.list_message_ids_in_inbox.assert_any_call(
            "page_token_1", max_results=MAX_RESULTS_PER_PAGE
        )
    
    def test_fetch_and_store_emails_max_pages_reached(self):
        """Test fetching stops when max pages is reached"""
        # Mock data
        message_ids = ["msg1", "msg2"]
        email_data = {
            "msg1": {"gmail_message_id": "msg1", "subject": "Test 1"},
            "msg2": {"gmail_message_id": "msg2", "subject": "Test 2"}
        }
        
        # Mock Gmail API responses - always return a page token
        self.mock_gmail_service.list_message_ids_in_inbox.return_value = (message_ids, "page_token")
        self.mock_gmail_service.get_messages_for_rules_batch.return_value = email_data
        
        # Mock database response
        self.mock_db_service.upsert_emails.return_value = 2
        
        # Execute with max_pages=2
        result = self.service.fetch_and_store_emails(max_pages=2)
        
        # Assertions
        assert result == 4  # 2 pages * 2 emails each
        assert self.mock_gmail_service.list_message_ids_in_inbox.call_count == 2
        assert self.mock_gmail_service.get_messages_for_rules_batch.call_count == 2
        assert self.mock_db_service.upsert_emails.call_count == 2
    
    def test_fetch_and_store_emails_custom_parameters(self):
        """Test fetching with custom page size and results per page"""
        # Mock data
        message_ids = ["msg1"]
        email_data = {"msg1": {"gmail_message_id": "msg1", "subject": "Test 1"}}
        
        # Mock Gmail API responses
        self.mock_gmail_service.list_message_ids_in_inbox.return_value = (message_ids, None)
        self.mock_gmail_service.get_messages_for_rules_batch.return_value = email_data
        
        # Mock database response
        self.mock_db_service.upsert_emails.return_value = 1
        
        # Execute with custom parameters
        result = self.service.fetch_and_store_emails(max_pages=5, max_results_per_page=100)
        
        # Assertions
        assert result == 1
        self.mock_gmail_service.list_message_ids_in_inbox.assert_called_once_with(
            None, max_results=100
        )
    
    def test_store_single_page(self):
        """Test storing a single page of emails"""
        # Mock data
        message_ids = ["msg1", "msg2"]
        email_data = {
            "msg1": {"gmail_message_id": "msg1", "subject": "Test 1"},
            "msg2": {"gmail_message_id": "msg2", "subject": "Test 2"}
        }
        
        # Mock Gmail API responses
        self.mock_gmail_service.list_message_ids_in_inbox.return_value = (message_ids, None)
        self.mock_gmail_service.get_messages_for_rules_batch.return_value = email_data
        
        # Mock database response
        self.mock_db_service.upsert_emails.return_value = 2
        
        # Execute
        result = self.service.store_single_page(max_results=50)
        
        # Assertions
        assert result == 2
        self.mock_gmail_service.list_message_ids_in_inbox.assert_called_once_with(
            None, max_results=50
        )
        self.mock_gmail_service.get_messages_for_rules_batch.assert_called_once_with(message_ids)
        # Check that upsert_emails was called with the correct data
        self.mock_db_service.upsert_emails.assert_called_once()
        call_args = self.mock_db_service.upsert_emails.call_args[0][0]
        assert list(call_args) == list(email_data.values())
    
    def test_store_single_page_default_parameters(self):
        """Test storing single page with default parameters"""
        # Mock data
        message_ids = ["msg1"]
        email_data = {"msg1": {"gmail_message_id": "msg1", "subject": "Test 1"}}
        
        # Mock Gmail API responses
        self.mock_gmail_service.list_message_ids_in_inbox.return_value = (message_ids, None)
        self.mock_gmail_service.get_messages_for_rules_batch.return_value = email_data
        
        # Mock database response
        self.mock_db_service.upsert_emails.return_value = 1
        
        # Execute with default parameters
        result = self.service.store_single_page()
        
        # Assertions
        assert result == 1
        self.mock_gmail_service.list_message_ids_in_inbox.assert_called_once_with(
            None, max_results=MAX_RESULTS_PER_PAGE
        )
    
    def test_fetch_and_store_emails_empty_response(self):
        """Test handling empty response from Gmail API"""
        # Mock empty response
        self.mock_gmail_service.list_message_ids_in_inbox.return_value = ([], None)
        self.mock_gmail_service.get_messages_for_rules_batch.return_value = {}
        
        # Mock database response
        self.mock_db_service.upsert_emails.return_value = 0
        
        # Execute
        result = self.service.fetch_and_store_emails()
        
        # Assertions
        assert result == 0
        self.mock_gmail_service.list_message_ids_in_inbox.assert_called_once()
        self.mock_gmail_service.get_messages_for_rules_batch.assert_called_once_with([])
        # Check that upsert_emails was called with empty data
        self.mock_db_service.upsert_emails.assert_called_once()
        call_args = self.mock_db_service.upsert_emails.call_args[0][0]
        assert list(call_args) == []
    
    def test_fetch_and_store_emails_duplicate_message_ids(self):
        """Test handling duplicate message IDs in response"""
        # Mock data with duplicates
        message_ids = ["msg1", "msg1", "msg2"]  # Duplicate msg1
        email_data = {
            "msg1": {"gmail_message_id": "msg1", "subject": "Test 1"},
            "msg2": {"gmail_message_id": "msg2", "subject": "Test 2"}
        }
        
        # Mock Gmail API responses
        self.mock_gmail_service.list_message_ids_in_inbox.return_value = (message_ids, None)
        self.mock_gmail_service.get_messages_for_rules_batch.return_value = email_data
        
        # Mock database response
        self.mock_db_service.upsert_emails.return_value = 2
        
        # Execute
        result = self.service.fetch_and_store_emails()
        
        # Assertions
        assert result == 2
        # Should still call with the original message_ids (duplicates handled by Gmail API)
        self.mock_gmail_service.get_messages_for_rules_batch.assert_called_once_with(message_ids)
