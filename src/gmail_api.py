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


# Read-only scope is sufficient to list and read messages
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.modify"]

def _paths() -> tuple[str, str]:
    creds_path = os.getenv("GOOGLE_CREDENTIALS_FILE", os.path.join(os.getcwd(), "credentials.json"))
    token_path = os.getenv("GOOGLE_TOKEN_FILE", os.path.join(os.getcwd(), "token.json"))
    return creds_path, token_path


def _save_credentials_to_file(token_path: str, creds: Credentials) -> None:
    with open(token_path, "w") as token_file:
        token_file.write(creds.to_json())


def _load_credentials() -> Credentials:
    _, token_path = _paths()
    creds: Optional[Credentials] = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds_path, token_path = _paths()
            if not os.path.exists(creds_path):
                raise FileNotFoundError(
                    "credentials.json not found. Download OAuth client credentials from Google Cloud Console and place it in the project root."
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save refreshed/new credentials to token file
        _, token_path = _paths()
        _save_credentials_to_file(token_path, creds)

    return creds


def get_gmail_service():
    creds = _load_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return service


def list_message_ids_in_inbox(service, next_page_token: str | None = None, max_results: int = 50) -> List[str]:
    results = (
        service.users()
        .messages()
        .list(userId="me", labelIds=["INBOX"], maxResults=max_results, pageToken=next_page_token)
        .execute()
    )
    messages = results.get("messages", [])
    # breakpoint()
    return (list(m["id"] for m in messages)), results.get("nextPageToken")


def get_message_details(service, message_id: str) -> Dict[str, Any]:
    msg = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["Subject", "From"],
        )
        .execute()
    )

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

    return {
        "gmail_message_id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "history_id": int(msg.get("historyId")) if msg.get("historyId") is not None else None,
        "subject": header("Subject"),
        "from_address": header("From"),
        "to_address": header("To"),
        "snippet": msg.get("snippet"),
        "label_ids": msg.get("labelIds", []),
        "internal_date": internal_dt,
    }


# ---------- Helpers for rule processing and actions ----------

def _b64url_decode(data: str) -> bytes:
    # Gmail returns base64url without padding
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _collect_text_from_payload(payload: dict) -> str:
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
                decoded = _b64url_decode(data).decode("utf-8", errors="ignore")
                if mime_type == "text/html":
                    decoded = html.unescape(decoded)
                texts.append(decoded)
            except Exception:
                pass
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    return "\n".join(texts)


def _parse_message_for_rules(msg: Dict[str, Any]) -> Dict[str, Any]:
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

    message_text = _collect_text_from_payload(msg.get("payload"))

    return {
        "gmail_message_id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "label_ids": msg.get("labelIds", []),
        "from_address": header("From"),
        "to_address": header("To"),
        "subject": header("Subject") or "",
        "snippet": msg.get("snippet"),
        "received_at": internal_dt,
    }


def get_messages_for_rules_batch(service, message_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}

    def make_batch(ids: List[str]):
        batch = service.new_batch_http_request()

        def callback(request_id, response, exception):
            if exception is None and isinstance(response, dict):
                try:
                    results[request_id] = _parse_message_for_rules(response)
                except Exception:
                    print(f"Error parsing message {request_id}")
                    pass
        for mid in ids:
            req = (
                service.users()
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


def _get_all_labels_map(service) -> Dict[str, str]:
    # name -> id
    labels = (
        service.users()
        .labels()
        .list(userId="me")
        .execute()
        .get("labels", [])
    )
    return {label.get("name"): label.get("id") for label in labels if label.get("id")}


def ensure_label_exists(service, label_name: str) -> str:
    labels_map = _get_all_labels_map(service)
    if label_name in labels_map:
        return labels_map[label_name]
    created = (
        service.users()
        .labels()
        .create(userId="me", body={"name": label_name, "labelListVisibility": "labelShow"})
        .execute()
    )
    return created.get("id")


def modify_message_labels(service, message_ids: List[str], add: List[str] | None = None, remove: List[str] | None = None) -> None:
    body: Dict[str, List[str]] = {}
    body["ids"] = message_ids
    if add:
        body["addLabelIds"] = add
    if remove:
        body["removeLabelIds"] = remove
    (
        service.users()
        .messages()
        .batchModify(userId="me", body=body)
        .execute()
    )


def mark_as_read(service, message_ids: List[str]) -> None:
    if(len(message_ids) > 1000):
        raise ValueError("Cannot mark more than 1000 messages at once")

    modify_message_labels(service, message_ids, remove=["UNREAD"])


def mark_as_unread(service, message_ids: List[str]) -> None:
    modify_message_labels(service, message_ids, add=["UNREAD"])


def move_message_to_label(service, message_ids: List[str], label_name: str, remove_from_inbox: bool = True) -> None:
    label_id = ensure_label_exists(service, label_name)
    remove_ids: List[str] = ["INBOX"] if remove_from_inbox else []
    modify_message_labels(service, message_ids, add=[label_id], remove=remove_ids)


