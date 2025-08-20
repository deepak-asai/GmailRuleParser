from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import base64
import html
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from bs4 import BeautifulSoup
from src.config import get_logger
import re

# Set up logger for this module
logger = get_logger(__name__)


# Read-only scope is sufficient to list and read messages
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.modify"]

def singleton(cls):
    """
    Decorator to make a class a singleton.
    Ensures only one instance of the class exists.
    """
    instances = {}
    
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance

@singleton
class GmailApiService:
    """Gmail API service singleton for managing emails and labels"""
    
    def __init__(self, service = None):
        """Initialize Gmail API service"""
        self.service = service or self._load_credentials()
    
    def list_message_ids_in_inbox(self, next_page_token: str | None = None, max_results: int = 50) -> tuple[List[str], str | None]:
        """
        List message IDs from inbox with pagination support.
        
        Args:
            next_page_token: Token for next page of results
            max_results: Maximum number of results per page
            
        Returns:
            Tuple of (message_ids, next_page_token)
        """
        results = (
            self.service.users()
            .messages()
            .list(userId="me", labelIds=["INBOX"], maxResults=max_results, pageToken=next_page_token)
            .execute()
        )
        messages = results.get("messages", [])
        return (list(m["id"] for m in messages)), results.get("nextPageToken")

    def get_messages_for_rules_batch(self, message_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get messages in batch for rule processing.
        
        Args:
            message_ids: List of Gmail message IDs
            
        Returns:
            Dictionary mapping message_id to message data
        """
        results: Dict[str, Dict[str, Any]] = {}

        def make_batch(ids: List[str]):
            batch = self.service.new_batch_http_request()

            def callback(request_id, response, exception):
                if exception is None and isinstance(response, dict):
                    try:
                        results[request_id] = self._parse_message_for_rules(response)
                    except Exception:
                        logger.error(f"Error parsing message {request_id}")
                        pass
            
            for mid in ids:
                req = (
                    self.service.users()
                    .messages()
                    .get(userId="me", id=mid, format="full")
                )
                batch.add(req, request_id=mid, callback=callback)
            batch.execute()

        chunk: List[str] = []
        for mid in message_ids:
            chunk.append(mid)
            if len(chunk) == 20:
                make_batch(chunk)
                chunk = []
        if chunk:
            make_batch(chunk)

        return results

    def _get_all_labels_map(self) -> Dict[str, str]:
        """Get mapping of label names to IDs"""
        # name -> id
        labels = (
            self.service.users()
            .labels()
            .list(userId="me")
            .execute()
            .get("labels", [])
        )
        return {label.get("name"): label.get("id") for label in labels if label.get("id")}

    def ensure_label_exists(self, label_name: str) -> str:
        """
        Ensure a label exists, creating it if necessary.
        
        Args:
            label_name: Name of the label
            
        Returns:
            Label ID
        """
        labels_map = self._get_all_labels_map()
        if label_name in labels_map:
            return labels_map[label_name]
        
        created = (
            self.service.users()
            .labels()
            .create(userId="me", body={"name": label_name, "labelListVisibility": "labelShow"})
            .execute()
        )
        return created.get("id")

    def modify_message_labels(self, message_ids: List[str], add: List[str] | None = None, remove: List[str] | None = None) -> None:
        """
        Modify labels on messages.
        
        Args:
            message_ids: List of message IDs to modify
            add: Labels to add
            remove: Labels to remove
        """
        body: Dict[str, List[str]] = {}
        body["ids"] = message_ids
        if add:
            body["addLabelIds"] = add
        if remove:
            body["removeLabelIds"] = remove
        
        (
            self.service.users()
            .messages()
            .batchModify(userId="me", body=body)
            .execute()
        )

    def mark_as_read(self, message_ids: List[str]) -> None:
        """
        Mark messages as read.
        
        Args:
            message_ids: List of message IDs to mark as read
            
        Raises:
            ValueError: If more than 1000 messages are provided
        """
        if len(message_ids) > 1000:
            raise ValueError("Cannot mark more than 1000 messages at once")

        self.modify_message_labels(message_ids, remove=["UNREAD"])

    def mark_as_unread(self, message_ids: List[str]) -> None:
        """
        Mark messages as unread.
        
        Args:
            message_ids: List of message IDs to mark as unread
        """
        self.modify_message_labels(message_ids, add=["UNREAD"])

    def move_message_to_label(self, message_ids: List[str], label_name: str, remove_from_inbox: bool = True) -> None:
        """
        Move messages to a label.
        
        Args:
            message_ids: List of message IDs to move
            label_name: Name of the label to move to
            remove_from_inbox: Whether to remove from INBOX
        """
        label_id = self.ensure_label_exists(label_name)
        remove_ids: List[str] = ["INBOX"] if remove_from_inbox else []
        self.modify_message_labels(message_ids, add=[label_id], remove=remove_ids)

    def _b64url_decode(self, data: str) -> bytes:
        """Decode base64url data without padding"""
        # Gmail returns base64url without padding
        padding = '=' * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + padding)

    def _strip_html(self, html_content: str) -> str:
        """
        Strip HTML tags from content using BeautifulSoup.
        
        Args:
            html_content: HTML content to strip
            
        Returns:
            Plain text content with HTML tags removed
        """
        if not html_content:
            return ""
        
        try:
            # Parse HTML and extract text
            soup = BeautifulSoup(html_content, 'html.parser')
            # Get text content, removing extra whitespace
            text = soup.get_text(separator=' ', strip=True)
            # Clean up multiple spaces and newlines
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        except Exception as e:
            logger.warning(f"Error stripping HTML: {e}")
            # Fallback to simple HTML unescape if BeautifulSoup fails
            return html.unescape(html_content)

    def _collect_text_from_payload(self, payload: dict) -> str:
        """Collect text content from message payload"""
        texts: List[str] = []
        if not payload:
            return ""

        def walk(part: dict) -> None:
            if not part:
                return
            mime_type = part.get("mimeType")
            body = part.get("body", {})
            data = body.get("data")
            if data and mime_type in {"text/plain", "text/html"}:
                try:
                    decoded = self._b64url_decode(data).decode("utf-8", errors="ignore")
                    if mime_type == "text/html":
                        # Strip HTML tags using BeautifulSoup
                        decoded = self._strip_html(decoded)
                    else:
                        # Clean up extra spaces and newlines for plain text as well
                        decoded = re.sub(r'\s+', ' ', decoded).strip()
                    texts.append(decoded)
                except Exception:
                    pass
            for child in part.get("parts", []) or []:
                walk(child)

        walk(payload)
        return "\n".join(texts)

    def _parse_message_for_rules(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """Parse message for rule processing"""
        def header(name: str) -> Optional[str]:
            for h in msg.get("payload", {}).get("headers", []):
                if h.get("name") == name:
                    return h.get("value")
            return None

        internal_date_ms = msg.get("internalDate")
        internal_dt = None
        if internal_date_ms is not None:
            try:
                internal_dt = datetime.fromtimestamp(int(internal_date_ms) / 1000.0, tz=timezone.utc)
            except Exception:
                internal_dt = None

        message_text = self._collect_text_from_payload(msg.get("payload"))

        return {
            "gmail_message_id": msg.get("id"),
            "thread_id": msg.get("threadId"),
            "label_ids": msg.get("labelIds", []),
            "from_address": header("From"),
            "to_address": header("To"),
            "subject": header("Subject") or "",
            "message": message_text,
            "received_at": internal_dt,
        }

    def _paths(self) -> tuple[str, str]:
        """Get paths for credentials and token files"""
        creds_path = os.getenv("GOOGLE_CREDENTIALS_FILE", os.path.join(os.getcwd(), "credentials.json"))
        token_path = os.getenv("GOOGLE_TOKEN_FILE", os.path.join(os.getcwd(), "token.json"))
        return creds_path, token_path

    def _save_credentials_to_file(self, token_path: str, creds: Credentials) -> None:
        """Save credentials to token file"""
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    def _load_credentials(self) -> Any:
        """Load and refresh OAuth credentials, return Gmail service"""
        _, token_path = self._paths()
        creds: Optional[Credentials] = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds_path, token_path = self._paths()
                if not os.path.exists(creds_path):
                    raise FileNotFoundError(
                        "credentials.json not found. Download OAuth client credentials from Google Cloud Console and place it in the project root."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save refreshed/new credentials to token file
            _, token_path = self._paths()
            self._save_credentials_to_file(token_path, creds)

        return build("gmail", "v1", credentials=creds, cache_discovery=False)