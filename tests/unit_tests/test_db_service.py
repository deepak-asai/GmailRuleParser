import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.db_service import DatabaseService, singleton
from src.models import Email


class MockEmail:
    """Mock Email model for testing"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestDatabaseService:
    """Test cases for DatabaseService class"""
    
    def setup_method(self):
        """Set up test fixtures before each test method"""
        # Clear singleton instances before each test
        if hasattr(DatabaseService, '__wrapped__'):
            DatabaseService.__wrapped__.instances = {}
        
        # Create mock engine and session
        self.mock_engine = Mock()
        self.mock_session = Mock(spec=Session)
        
        # Make the mock session support context manager protocol
        self.mock_session.__enter__ = Mock(return_value=self.mock_session)
        self.mock_session.__exit__ = Mock(return_value=None)
        
        # Patch the database creation
        with patch('src.db_service.create_engine_for_url', return_value=self.mock_engine):
            self.db_service = DatabaseService()
        
        # Patch the get_session method to return our mock session
        self.db_service.get_session = Mock(return_value=self.mock_session)
    
    def test_singleton_behavior(self):
        """Test that DatabaseService behaves as a singleton"""
        # Clear singleton instances
        if hasattr(DatabaseService, '__wrapped__'):
            DatabaseService.__wrapped__.instances = {}
        
        # Create first instance
        with patch('src.db_service.create_engine_for_url', return_value=self.mock_engine):
            service1 = DatabaseService()
        
        # Create second instance - should be the same due to singleton
        with patch('src.db_service.create_engine_for_url', return_value=Mock()):
            service2 = DatabaseService()
        
        # Both should be the same instance due to singleton behavior
        assert service1 is service2
        assert service1.engine is service2.engine
    
    def test_get_session(self):
        """Test getting a database session"""
        # Reset the mock to test the actual method
        self.db_service.get_session = Mock(return_value=self.mock_session)
        session = self.db_service.get_session()
        assert session is self.mock_session
    
    @patch('src.db_service.pg_insert')
    def test_upsert_emails_single_batch(self, mock_pg_insert):
        """Test upserting emails in a single batch"""
        # Mock the insert statement
        mock_stmt = Mock()
        mock_pg_insert.return_value.values.return_value.on_conflict_do_nothing.return_value.returning.return_value = mock_stmt
        
        # Mock session execution
        mock_result = Mock()
        mock_result.scalars.return_value = [1, 2, 3]  # Return 3 inserted IDs
        self.mock_session.execute.return_value = mock_result
        
        # Test data
        email_rows = [
            {"gmail_message_id": "msg1", "subject": "Test 1"},
            {"gmail_message_id": "msg2", "subject": "Test 2"},
            {"gmail_message_id": "msg3", "subject": "Test 3"}
        ]
        
        inserted_count = self.db_service.upsert_emails(email_rows, batch_size=1000)
        
        assert inserted_count == 3
        self.mock_session.commit.assert_called_once()
    
    @patch('src.db_service.pg_insert')
    def test_upsert_emails_multiple_batches(self, mock_pg_insert):
        """Test upserting emails across multiple batches"""
        # Mock the insert statement
        mock_stmt = Mock()
        mock_pg_insert.return_value.values.return_value.on_conflict_do_nothing.return_value.returning.return_value = mock_stmt
        
        # Mock session execution - return different counts for each batch
        mock_result1 = Mock()
        mock_result1.scalars.return_value = [1, 2]  # First batch: 2 inserted
        mock_result2 = Mock()
        mock_result2.scalars.return_value = [3]     # Second batch: 1 inserted
        
        self.mock_session.execute.side_effect = [mock_result1, mock_result2]
        
        # Test data - more than batch size
        email_rows = [
            {"gmail_message_id": f"msg{i}", "subject": f"Test {i}"}
            for i in range(1500)  # More than batch_size of 1000
        ]
        
        inserted_count = self.db_service.upsert_emails(email_rows, batch_size=1000)
        
        assert inserted_count == 3  # 2 + 1
        assert self.mock_session.commit.call_count == 2  # Called twice for two batches
    
    @patch('src.db_service.pg_insert')
    def test_upsert_emails_empty_batch(self, mock_pg_insert):
        """Test upserting empty email list"""
        inserted_count = self.db_service.upsert_emails([], batch_size=1000)
        
        assert inserted_count == 0
        self.mock_session.execute.assert_not_called()
        self.mock_session.commit.assert_not_called()
    
    def test_build_database_query_no_conditions(self):
        """Test building query with no conditions"""
        mock_rule = Mock()
        mock_rule.conditions = []
        mock_rule.predicate = "All"
        
        query = self.db_service.build_database_query(self.mock_session, mock_rule)
        
        # Should return base query without filters
        assert query is not None
    
    def test_build_database_query_from_field_contains(self):
        """Test building query with From field Contains condition"""
        mock_rule = Mock()
        mock_rule.conditions = [
            Mock(field="From", predicate="Contains", value="test@example.com")
        ]
        mock_rule.predicate = "All"
        
        query = self.db_service.build_database_query(self.mock_session, mock_rule)
        
        # Verify the query was built (we can't easily test the exact SQL without more complex mocking)
        assert query is not None
    
    def test_build_database_query_from_field_equals(self):
        """Test building query with From field Equals condition"""
        mock_rule = Mock()
        mock_rule.conditions = [
            Mock(field="From", predicate="Equals", value="exact@example.com")
        ]
        mock_rule.predicate = "All"
        
        query = self.db_service.build_database_query(self.mock_session, mock_rule)
        
        assert query is not None
    
    def test_build_database_query_subject_field(self):
        """Test building query with Subject field conditions"""
        mock_rule = Mock()
        mock_rule.conditions = [
            Mock(field="Subject", predicate="Contains", value="important")
        ]
        mock_rule.predicate = "All"
        
        query = self.db_service.build_database_query(self.mock_session, mock_rule)
        
        assert query is not None
    
    def test_build_database_query_message_field(self):
        """Test building query with Message field conditions"""
        mock_rule = Mock()
        mock_rule.conditions = [
            Mock(field="Message", predicate="Contains", value="urgent")
        ]
        mock_rule.predicate = "All"
        
        query = self.db_service.build_database_query(self.mock_session, mock_rule)
        
        assert query is not None
    
    def test_build_database_query_received_field_less_than_days(self):
        """Test building query with Received field LessThanDays condition"""
        mock_rule = Mock()
        mock_rule.conditions = [
            Mock(field="Received", predicate="LessThanDays", value="7")
        ]
        mock_rule.predicate = "All"
        
        query = self.db_service.build_database_query(self.mock_session, mock_rule)
        
        assert query is not None
    
    def test_build_database_query_received_field_greater_than_days(self):
        """Test building query with Received field GreaterThanDays condition"""
        mock_rule = Mock()
        mock_rule.conditions = [
            Mock(field="Received", predicate="GreaterThanDays", value="30")
        ]
        mock_rule.predicate = "All"
        
        query = self.db_service.build_database_query(self.mock_session, mock_rule)
        
        assert query is not None
    
    def test_build_database_query_received_field_invalid_value(self):
        """Test building query with Received field invalid value"""
        mock_rule = Mock()
        mock_rule.conditions = [
            Mock(field="Received", predicate="LessThanDays", value="invalid")
        ]
        mock_rule.predicate = "All"
        
        query = self.db_service.build_database_query(self.mock_session, mock_rule)
        
        # Should skip invalid condition and return base query
        assert query is not None
    
    def test_build_database_query_invalid_field(self):
        """Test building query with invalid field"""
        mock_rule = Mock()
        mock_rule.conditions = [
            Mock(field="InvalidField", predicate="Contains", value="test")
        ]
        mock_rule.predicate = "All"
        
        with pytest.raises(ValueError, match="Invalid field: InvalidField"):
            self.db_service.build_database_query(self.mock_session, mock_rule)
    
    def test_build_database_query_all_predicate(self):
        """Test building query with 'All' predicate (AND logic)"""
        mock_rule = Mock()
        mock_rule.conditions = [
            Mock(field="From", predicate="Contains", value="test@example.com"),
            Mock(field="Subject", predicate="Contains", value="important")
        ]
        mock_rule.predicate = "All"
        
        query = self.db_service.build_database_query(self.mock_session, mock_rule)
        
        assert query is not None
    
    def test_build_database_query_any_predicate(self):
        """Test building query with 'Any' predicate (OR logic)"""
        mock_rule = Mock()
        mock_rule.conditions = [
            Mock(field="From", predicate="Contains", value="test@example.com"),
            Mock(field="Subject", predicate="Contains", value="important")
        ]
        mock_rule.predicate = "Any"
        
        query = self.db_service.build_database_query(self.mock_session, mock_rule)
        
        assert query is not None
    
    def test_get_matching_emails(self):
        """Test getting matching emails from database"""
        # Mock rule
        mock_rule = Mock()
        mock_rule.conditions = [
            Mock(field="From", predicate="Contains", value="test@example.com")
        ]
        mock_rule.predicate = "All"
        
        # Mock query result
        mock_emails = [
            MockEmail(id=1, gmail_message_id="msg1", subject="Test 1"),
            MockEmail(id=2, gmail_message_id="msg2", subject="Test 2")
        ]
        
        # Mock the query building and execution
        mock_query = Mock()
        mock_query.offset.return_value.limit.return_value.all.return_value = mock_emails
        
        with patch.object(self.db_service, 'build_database_query', return_value=mock_query):
            result = self.db_service.get_matching_emails(mock_rule, offset=10, limit=20)
        
        assert result == mock_emails
        mock_query.offset.assert_called_once_with(10)
        mock_query.offset().limit.assert_called_once_with(20)
    
    def test_get_matching_emails_default_parameters(self):
        """Test getting matching emails with default parameters"""
        # Mock rule
        mock_rule = Mock()
        mock_rule.conditions = []
        mock_rule.predicate = "All"
        
        # Mock query result
        mock_emails = [MockEmail(id=1, gmail_message_id="msg1", subject="Test")]
        
        # Mock the query building and execution
        mock_query = Mock()
        mock_query.offset.return_value.limit.return_value.all.return_value = mock_emails
        
        with patch.object(self.db_service, 'build_database_query', return_value=mock_query):
            result = self.db_service.get_matching_emails(mock_rule)
        
        assert result == mock_emails
        mock_query.offset.assert_called_once_with(0)  # Default offset
        mock_query.offset().limit.assert_called_once_with(20)  # Default limit
