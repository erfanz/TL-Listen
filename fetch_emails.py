import os
import google.auth.exceptions
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import google_auth_httplib2
import httplib2
import base64
from email.utils import parsedate_to_datetime

import config


def get_gmail_service():
    """Authenticate and return a Gmail API service instance."""
    creds = None
    if os.path.exists(config.GMAIL_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            config.GMAIL_TOKEN_FILE, config.GMAIL_SCOPES
        )
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except google.auth.exceptions.RefreshError:
                creds = None
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GMAIL_CREDENTIALS_FILE, config.GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(config.GMAIL_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    if config.SSL_CA_FILE:
        http = httplib2.Http(ca_certs=config.SSL_CA_FILE)
        authed_http = google_auth_httplib2.AuthorizedHttp(creds, http=http)
        return build("gmail", "v1", http=authed_http)
    return build("gmail", "v1", credentials=creds)


def _get_label_id(service, label_name):
    """Resolve a label name to its ID."""
    results = service.users().labels().list(userId="me").execute()
    for label in results.get("labels", []):
        if label["name"].lower() == label_name.lower():
            return label["id"]
    return None


def _decode_body(payload):
    """Recursively extract text/html or text/plain from a message payload."""
    html_parts = []
    text_parts = []

    if "parts" in payload:
        for part in payload["parts"]:
            h, t = _decode_body(part)
            html_parts.extend(h)
            text_parts.extend(t)
    else:
        mime = payload.get("mimeType", "")
        data = payload.get("body", {}).get("data", "")
        if data:
            decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            if "html" in mime:
                html_parts.append(decoded)
            elif "plain" in mime:
                text_parts.append(decoded)

    return html_parts, text_parts


def fetch_digest_emails(mark_read=True):
    """
    Fetch unread emails with the configured digest label.
    Returns list of dicts: {id, subject, html, text}
    """
    service = get_gmail_service()
    label_id = _get_label_id(service, config.GMAIL_LABEL)
    if not label_id:
        print(f"⚠️  Label '{config.GMAIL_LABEL}' not found in Gmail.")
        return []

    query = f"is:unread label:{config.GMAIL_LABEL}"
    results = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=50)
        .execute()
    )
    message_ids = results.get("messages", [])
    if not message_ids:
        print("No new digest emails found.")
        return []

    emails = []
    for msg_ref in message_ids:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_ref["id"], format="full")
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        subject = headers.get("Subject", "(no subject)")
        sender = headers.get("From", "")
        raw_date = headers.get("Date", "")

        # Format date as "Day, DD Mon YYYY"
        date = ""
        if raw_date:
            try:
                parsed_date = parsedate_to_datetime(raw_date)
                date = parsed_date.strftime("%a, %d %b %Y")
            except (ValueError, TypeError):
                date = raw_date

        html_parts, text_parts = _decode_body(msg["payload"])

        emails.append(
            {
                "id": msg_ref["id"],
                "subject": subject,
                "from": sender,
                "date": date,
                "html": "\n".join(html_parts),
                "text": "\n".join(text_parts),
            }
        )

        if mark_read:
            service.users().messages().modify(
                userId="me",
                id=msg_ref["id"],
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()

    print(f"📬 Fetched {len(emails)} digest email(s).")
    return emails
