import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict

from src.process_rules import RuleProcessorService, MAX_MESSAGES_TO_PROCESS
from src.rules import Rule, Condition


class TestRuleProcessorService:
    """Test cases for RuleProcessorService class"""
    
    def setup_method(self):
        """Set up test fixtures before each test method"""
        self.mock_gmail_service = Mock()
        self.mock_db_service = Mock()
        self.service = RuleProcessorService(
            gmail_api_service=self.mock_gmail_service,
            db_service=self.mock_db_service
        )
    
    def test_init_with_services(self):
        """Test initialization with provided services"""
        service = RuleProcessorService(
            gmail_api_service=self.mock_gmail_service,
            db_service=self.mock_db_service
        )
        
        assert service.gmail_api_service == self.mock_gmail_service
        assert service.db_service == self.mock_db_service
    
    @patch('src.process_rules.GmailApiService')
    @patch('src.process_rules.DatabaseService')
    def test_init_without_services(self, mock_db_class, mock_gmail_class):
        """Test initialization without provided services"""
        mock_gmail_instance = Mock()
        mock_db_instance = Mock()
        mock_gmail_class.return_value = mock_gmail_instance
        mock_db_class.return_value = mock_db_instance
        
        service = RuleProcessorService()
        
        assert service.gmail_api_service == mock_gmail_instance
        assert service.db_service == mock_db_instance
        mock_gmail_class.assert_called_once()
        mock_db_class.assert_called_once()
    
    def test_apply_actions_mark_read(self):
        """Test applying mark as read action"""
        message_ids = ["msg1", "msg2"]
        actions = [{"mark": "read"}]
        
        self.service.apply_actions(message_ids, actions)
        
        self.mock_gmail_service.mark_as_read.assert_called_once_with(message_ids)
        self.mock_gmail_service.mark_as_unread.assert_not_called()
    
    def test_apply_actions_mark_unread(self):
        """Test applying mark as unread action"""
        message_ids = ["msg1", "msg2"]
        actions = [{"mark": "unread"}]
        
        self.service.apply_actions(message_ids, actions)
        
        self.mock_gmail_service.mark_as_unread.assert_called_once_with(message_ids)
        self.mock_gmail_service.mark_as_read.assert_not_called()
    
    def test_apply_actions_move_to_label(self):
        """Test applying move to label action"""
        message_ids = ["msg1", "msg2"]
        actions = [{"move": "Important"}]
        
        self.service.apply_actions(message_ids, actions)
        
        self.mock_gmail_service.move_message_to_label.assert_called_once_with(
            message_ids, "Important", False
        )
    
    def test_apply_actions_multiple_actions(self):
        """Test applying multiple actions"""
        message_ids = ["msg1", "msg2"]
        actions = [
            {"mark": "read"},
            {"move": "Important"}
        ]
        
        self.service.apply_actions(message_ids, actions)
        
        self.mock_gmail_service.mark_as_read.assert_called_once_with(message_ids)
        self.mock_gmail_service.move_message_to_label.assert_called_once_with(
            message_ids, "Important", False
        )
    
    def test_apply_actions_empty_message_ids(self):
        """Test applying actions with empty message IDs"""
        message_ids = []
        actions = [{"mark": "read"}]
        
        self.service.apply_actions(message_ids, actions)
        
        # Should still call the method even with empty list
        self.mock_gmail_service.mark_as_read.assert_called_once_with([])
    
    def test_apply_actions_no_actions(self):
        """Test applying actions with no actions"""
        message_ids = ["msg1", "msg2"]
        actions = []
        
        self.service.apply_actions(message_ids, actions)
        
        # Should not call any Gmail API methods
        self.mock_gmail_service.mark_as_read.assert_not_called()
        self.mock_gmail_service.mark_as_unread.assert_not_called()
        self.mock_gmail_service.move_message_to_label.assert_not_called()
    
    def test_apply_actions_invalid_mark_action(self):
        """Test applying invalid mark action"""
        message_ids = ["msg1", "msg2"]
        actions = [{"mark": "invalid"}]
        
        self.service.apply_actions(message_ids, actions)
        
        # Should not call any mark methods
        self.mock_gmail_service.mark_as_read.assert_not_called()
        self.mock_gmail_service.mark_as_unread.assert_not_called()
    
    def test_apply_actions_empty_move_label(self):
        """Test applying move action with empty label"""
        message_ids = ["msg1", "msg2"]
        actions = [{"move": ""}]
        
        self.service.apply_actions(message_ids, actions)
        
        # Should not call move method with empty label
        self.mock_gmail_service.move_message_to_label.assert_not_called()
    
    def test_apply_actions_whitespace_move_label(self):
        """Test applying move action with whitespace-only label"""
        message_ids = ["msg1", "msg2"]
        actions = [{"move": "   "}]
        
        self.service.apply_actions(message_ids, actions)
        
        # Should not call move method with whitespace-only label
        self.mock_gmail_service.move_message_to_label.assert_not_called()
    
    def test_process_emails_with_rules_single_batch(self):
        """Test processing emails with single batch"""
        # Create mock rule
        rule = Rule(
            conditions=[
                Condition(field="Subject", predicate="Contains", value="test")
            ],
            predicate="Any",
            actions=[{"mark": "read"}]
        )
        
        # Create mock emails
        mock_email1 = Mock()
        mock_email1.gmail_message_id = "msg1"
        mock_email1.id = 1
        
        mock_email2 = Mock()
        mock_email2.gmail_message_id = "msg2"
        mock_email2.id = 2
        
        emails = [mock_email1, mock_email2]
        
        # Mock database service to return emails only once, then empty
        self.mock_db_service.get_matching_emails.side_effect = [
            emails,  # First call returns emails
            []       # Second call returns empty (no more emails)
        ]
        
        # Execute
        result = self.service.process_emails_with_rules(rule, max_messages=10)
        
        # Assertions
        assert result == 2
        assert self.mock_db_service.get_matching_emails.call_count == 2
        self.mock_db_service.get_matching_emails.assert_any_call(
            rule, offset=0, limit=10
        )
        self.mock_db_service.get_matching_emails.assert_any_call(
            rule, offset=2, limit=10
        )
        self.mock_gmail_service.mark_as_read.assert_called_once_with(["msg1", "msg2"])
    
    def test_process_emails_with_rules_multiple_batches(self):
        """Test processing emails with multiple batches"""
        # Create mock rule
        rule = Rule(
            conditions=[
                Condition(field="Subject", predicate="Contains", value="test")
            ],
            predicate="Any",
            actions=[{"mark": "read"}]
        )
        
        # Create mock emails for first batch
        mock_email1 = Mock()
        mock_email1.gmail_message_id = "msg1"
        mock_email1.id = 1
        
        mock_email2 = Mock()
        mock_email2.gmail_message_id = "msg2"
        mock_email2.id = 2
        
        # Create mock emails for second batch
        mock_email3 = Mock()
        mock_email3.gmail_message_id = "msg3"
        mock_email3.id = 3
        
        # Mock database service to return emails in batches
        self.mock_db_service.get_matching_emails.side_effect = [
            [mock_email1, mock_email2],  # First batch
            [mock_email3],               # Second batch
            []                           # No more emails
        ]
        
        # Execute
        result = self.service.process_emails_with_rules(rule, max_messages=2)
        
        # Assertions
        assert result == 3
        assert self.mock_db_service.get_matching_emails.call_count == 3
        
        # Check first batch call
        self.mock_db_service.get_matching_emails.assert_any_call(
            rule, offset=0, limit=2
        )
        # Check second batch call
        self.mock_db_service.get_matching_emails.assert_any_call(
            rule, offset=2, limit=2
        )
        # Check third batch call (empty)
        self.mock_db_service.get_matching_emails.assert_any_call(
            rule, offset=3, limit=2
        )
        
        # Check actions were applied for both batches
        assert self.mock_gmail_service.mark_as_read.call_count == 2
        self.mock_gmail_service.mark_as_read.assert_any_call(["msg1", "msg2"])
        self.mock_gmail_service.mark_as_read.assert_any_call(["msg3"])
    
    def test_process_emails_with_rules_no_matching_emails(self):
        """Test processing when no emails match the rule"""
        # Create mock rule
        rule = Rule(
            conditions=[
                Condition(field="Subject", predicate="Contains", value="test")
            ],
            predicate="Any",
            actions=[{"mark": "read"}]
        )
        
        # Mock database service to return no emails
        self.mock_db_service.get_matching_emails.return_value = []
        
        # Execute
        result = self.service.process_emails_with_rules(rule)
        
        # Assertions
        assert result == 0
        self.mock_db_service.get_matching_emails.assert_called_once_with(
            rule, offset=0, limit=MAX_MESSAGES_TO_PROCESS
        )
        self.mock_gmail_service.mark_as_read.assert_not_called()
    
    def test_process_emails_with_rules_custom_batch_size(self):
        """Test processing with custom batch size"""
        # Create mock rule
        rule = Rule(
            conditions=[
                Condition(field="Subject", predicate="Contains", value="test")
            ],
            predicate="Any",
            actions=[{"mark": "read"}]
        )
        
        # Create mock email
        mock_email = Mock()
        mock_email.gmail_message_id = "msg1"
        mock_email.id = 1
        
        # Mock database service to return email only once, then empty
        self.mock_db_service.get_matching_emails.side_effect = [
            [mock_email],  # First call returns email
            []             # Second call returns empty (no more emails)
        ]
        
        # Execute with custom batch size
        result = self.service.process_emails_with_rules(rule, max_messages=50)
        
        # Assertions
        assert result == 1
        assert self.mock_db_service.get_matching_emails.call_count == 2
        self.mock_db_service.get_matching_emails.assert_any_call(
            rule, offset=0, limit=50
        )
        self.mock_db_service.get_matching_emails.assert_any_call(
            rule, offset=1, limit=50
        )
    
    @patch('src.process_rules.load_rules_from_file')
    def test_process_rules_from_file(self, mock_load_rules):
        """Test processing rules from file"""
        # Create mock rule
        rule = Rule(
            conditions=[
                Condition(field="Subject", predicate="Contains", value="test")
            ],
            predicate="Any",
            actions=[{"mark": "read"}]
        )
        
        mock_load_rules.return_value = rule
        
        # Create mock email
        mock_email = Mock()
        mock_email.gmail_message_id = "msg1"
        mock_email.id = 1
        
        # Mock database service to return emails only once, then empty
        self.mock_db_service.get_matching_emails.side_effect = [
            [mock_email],  # First call returns email
            []             # Second call returns empty (no more emails)
        ]
        
        # Execute
        result = self.service.process_rules_from_file("test_rules.json")
        
        # Assertions
        assert result == 1
        mock_load_rules.assert_called_once_with("test_rules.json")
        assert self.mock_db_service.get_matching_emails.call_count == 2
        self.mock_db_service.get_matching_emails.assert_any_call(
            rule, offset=0, limit=MAX_MESSAGES_TO_PROCESS
        )
        self.mock_db_service.get_matching_emails.assert_any_call(
            rule, offset=1, limit=MAX_MESSAGES_TO_PROCESS
        )
    
    @patch('src.process_rules.load_rules_from_file')
    def test_process_rules_from_file_custom_batch_size(self, mock_load_rules):
        """Test processing rules from file with custom batch size"""
        # Create mock rule
        rule = Rule(
            conditions=[
                Condition(field="Subject", predicate="Contains", value="test")
            ],
            predicate="Any",
            actions=[{"mark": "read"}]
        )
        
        mock_load_rules.return_value = rule
        
        # Create mock email
        mock_email = Mock()
        mock_email.gmail_message_id = "msg1"
        mock_email.id = 1
        
        # Mock database service to return emails only once, then empty
        self.mock_db_service.get_matching_emails.side_effect = [
            [mock_email],  # First call returns email
            []             # Second call returns empty (no more emails)
        ]
        
        # Execute with custom batch size
        result = self.service.process_rules_from_file("test_rules.json", max_messages=100)
        
        # Assertions
        assert result == 1
        mock_load_rules.assert_called_once_with("test_rules.json")
        assert self.mock_db_service.get_matching_emails.call_count == 2
        self.mock_db_service.get_matching_emails.assert_any_call(
            rule, offset=0, limit=100
        )
        self.mock_db_service.get_matching_emails.assert_any_call(
            rule, offset=1, limit=100
        )
