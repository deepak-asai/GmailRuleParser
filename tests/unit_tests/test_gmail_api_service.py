import pytest
import base64
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, List, Any

from src.gmail_api_service import GmailApiService, singleton


class MockService:
    """Mock Gmail service for testing"""
    
    def __init__(self):
        self.mock_batch = Mock()
        self.mock_batch.execute = Mock()
        
    def users(self):
        return self
    
    def messages(self):
        return self
    
    def labels(self):
        return self
    
    def list(self, userId=None, labelIds=None, maxResults=None, pageToken=None):
        mock_request = Mock()
        if pageToken == "next_page":
            mock_request.execute.return_value = {
                "messages": [{"id": "msg3"}, {"id": "msg4"}],
                "nextPageToken": None
            }
        else:
            mock_request.execute.return_value = {
                "messages": [{"id": "msg1"}, {"id": "msg2"}],
                "nextPageToken": "next_page" if maxResults == 2 else None
            }
        return mock_request
    
    def get(self, userId=None, id=None, format=None):
        mock_request = Mock()
        mock_request.execute.return_value = self._get_message_response(id)
        return mock_request
    
    def _get_message_response(self, message_id: str) -> Dict[str, Any]:
        """Generate mock message response"""
        return {
            "id": message_id,
            "threadId": f"thread_{message_id}",
            "labelIds": ["INBOX", "UNREAD"],
            "snippet": f"Test snippet for {message_id}",
            "internalDate": "1640995200000",  # 2022-01-01 00:00:00 UTC
            "payload": {
                "headers": [
                    {"name": "From", "value": f"sender_{message_id}@example.com"},
                    {"name": "To", "value": "recipient@example.com"},
                    {"name": "Subject", "value": f"Test Subject {message_id}"}
                ],
                "mimeType": "text/plain",
                "body": {
                    "data": base64.urlsafe_b64encode(f"Test body for {message_id}".encode()).decode().rstrip("=")
                }
            }
        }
    
    def create(self, userId=None, body=None):
        mock_request = Mock()
        mock_request.execute.return_value = {"id": "label123", "name": body.get("name")}
        return mock_request
    
    def batchModify(self, userId=None, body=None):
        mock_request = Mock()
        mock_request.execute.return_value = {}
        return mock_request
    
    def new_batch_http_request(self):
        return MockBatchRequest()


class MockBatchRequest:
    """Mock batch request for testing"""
    
    def __init__(self):
        self.requests = []
    
    def add(self, request, request_id=None, callback=None):
        self.requests.append({
            'request': request,
            'request_id': request_id,
            'callback': callback
        })
    
    def execute(self):
        # Simulate batch execution by calling callbacks
        for req_info in self.requests:
            callback = req_info['callback']
            request_id = req_info['request_id']
            
            # Mock response for the message
            response = {
                "id": request_id,
                "threadId": f"thread_{request_id}",
                "labelIds": ["INBOX", "UNREAD"],
                "snippet": f"Test snippet for {request_id}",
                "internalDate": "1640995200000",
                "payload": {
                    "headers": [
                        {"name": "From", "value": f"sender_{request_id}@example.com"},
                        {"name": "To", "value": "recipient@example.com"},
                        {"name": "Subject", "value": f"Test Subject {request_id}"}
                    ],
                    "mimeType": "text/plain",
                    "body": {
                        "data": base64.urlsafe_b64encode(f"Test body for {request_id}".encode()).decode().rstrip("=")
                    }
                }
            }
            
            if callback:
                callback(request_id, response, None)


class TestGmailApiService:
    """Test cases for GmailApiService class"""
    
    def setup_method(self):
        """Set up test fixtures before each test method"""
        # Clear singleton instances before each test
        if hasattr(GmailApiService, '__wrapped__'):
            GmailApiService.__wrapped__.instances = {}
        
        self.mock_service = MockService()
        self.gmail_service = GmailApiService(service=self.mock_service)
    
    def test_singleton_behavior(self):
        """Test that GmailApiService behaves as a singleton"""
        # Clear singleton instances
        if hasattr(GmailApiService, '__wrapped__'):
            GmailApiService.__wrapped__.instances = {}
        
        # Create first instance
        service1 = GmailApiService(service=self.mock_service)
        
        # Create second instance - should be the same due to singleton
        service2 = GmailApiService(service=Mock())
        
        # Both should be the same instance due to singleton behavior
        assert service1 is service2
    
    def test_list_message_ids_in_inbox_first_page(self):
        """Test listing message IDs from inbox - first page"""
        message_ids, next_token = self.gmail_service.list_message_ids_in_inbox(max_results=50)
        
        assert message_ids == ["msg1", "msg2"]
        assert next_token is None
    
    def test_list_message_ids_in_inbox_with_pagination(self):
        """Test listing message IDs with pagination"""
        # First page
        message_ids, next_token = self.gmail_service.list_message_ids_in_inbox(max_results=2)
        assert message_ids == ["msg1", "msg2"]
        assert next_token == "next_page"
        
        # Second page
        message_ids, next_token = self.gmail_service.list_message_ids_in_inbox(
            next_page_token="next_page", max_results=2
        )
        assert message_ids == ["msg3", "msg4"]
        assert next_token is None
    
    def test_list_message_ids_empty_response(self):
        """Test handling empty message list"""
        # Create a mock service that returns empty messages
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = {"messages": []}
        
        # Set up the method chain properly
        mock_service.users.return_value.messages.return_value.list.return_value = mock_request
        
        # Patch the service property to use our mock
        with patch.object(self.gmail_service, 'service', mock_service):
            message_ids, next_token = self.gmail_service.list_message_ids_in_inbox()
        
        assert message_ids == []
        assert next_token is None
        
        # Verify the mock was called correctly
        mock_service.users.assert_called_once()
        mock_service.users().messages.assert_called_once()
        mock_service.users().messages().list.assert_called_once_with(
            userId="me", 
            labelIds=["INBOX"], 
            maxResults=50, 
            pageToken=None
        )
    
    def test_get_messages_for_rules_batch_single_message(self):
        """Test getting single message in batch"""
        results = self.gmail_service.get_messages_for_rules_batch(["msg1"])
        
        assert "msg1" in results
        message_data = results["msg1"]
        assert message_data["gmail_message_id"] == "msg1"
        assert message_data["from_address"] == "sender_msg1@example.com"
        assert message_data["subject"] == "Test Subject msg1"
    
    def test_get_messages_for_rules_batch_multiple_messages(self):
        """Test getting multiple messages in batch"""
        results = self.gmail_service.get_messages_for_rules_batch(["msg1", "msg2", "msg3"])
        
        assert len(results) == 3
        assert "msg1" in results
        assert "msg2" in results
        assert "msg3" in results
    
    def test_mark_as_read(self):
        """Test marking messages as read"""
        # Create a mock service with proper method chaining
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = mock_request
        
        # Patch the service property to use our mock
        with patch.object(self.gmail_service, 'service', mock_service):
            self.gmail_service.mark_as_read(["msg1", "msg2"])
        
        # Check that batchModify was called
        mock_service.users().messages().batchModify.assert_called_once()
        
        # Check the arguments passed to batchModify
        call_args = mock_service.users().messages().batchModify.call_args
        body = call_args[1]["body"]
        assert body["ids"] == ["msg1", "msg2"]
        assert body["removeLabelIds"] == ["UNREAD"]
    
    def test_mark_as_read_too_many_messages(self):
        """Test marking too many messages as read"""
        message_ids = [f"msg{i}" for i in range(1001)]
        
        with pytest.raises(ValueError, match="Cannot mark more than 1000 messages at once"):
            self.gmail_service.mark_as_read(message_ids)
    
    def test_mark_as_unread(self):
        """Test marking messages as unread"""
        # Create a mock service with proper method chaining
        mock_service = Mock()
        mock_request = Mock()
        mock_request.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = mock_request
        
        # Patch the service property to use our mock
        with patch.object(self.gmail_service, 'service', mock_service):
            self.gmail_service.mark_as_unread(["msg1", "msg2"])
        
        # Check that batchModify was called
        mock_service.users().messages().batchModify.assert_called_once()
        
        # Check the arguments passed to batchModify
        call_args = mock_service.users().messages().batchModify.call_args
        body = call_args[1]["body"]
        assert body["ids"] == ["msg1", "msg2"]
        assert body["addLabelIds"] == ["UNREAD"]
    
    def test_b64url_decode(self):
        """Test base64url decoding"""
        # Test string without padding
        data = "SGVsbG8gV29ybGQ"  # "Hello World" without padding
        result = self.gmail_service._b64url_decode(data)
        assert result == b"Hello World"
        
        # Test string that needs padding
        data = "SGVsbG8"  # "Hello" needs padding
        result = self.gmail_service._b64url_decode(data)
        assert result == b"Hello"
    
    def test_collect_text_from_payload_plain_text(self):
        """Test collecting text from plain text payload"""
        payload = {
            "mimeType": "text/plain",
            "body": {
                "data": base64.urlsafe_b64encode("Hello World".encode()).decode().rstrip("=")
            }
        }
        
        result = self.gmail_service._collect_text_from_payload(payload)
        assert result == "Hello World"
    
    def test_parse_message_for_rules(self):
        """Test parsing message for rules"""
        msg = {
            "id": "msg123",
            "threadId": "thread123",
            "labelIds": ["INBOX", "UNREAD"],
            "snippet": "Test snippet",
            "internalDate": "1640995200000",  # 2022-01-01 00:00:00 UTC
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "To", "value": "recipient@example.com"},
                    {"name": "Subject", "value": "Test Subject"}
                ]
            }
        }
        
        result = self.gmail_service._parse_message_for_rules(msg)
        
        assert result["gmail_message_id"] == "msg123"
        assert result["thread_id"] == "thread123"
        assert result["label_ids"] == ["INBOX", "UNREAD"]
        assert result["from_address"] == "sender@example.com"
        assert result["to_address"] == "recipient@example.com"
        assert result["subject"] == "Test Subject"
        assert result["snippet"] == "Test snippet"
        assert result["received_at"] == datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc)