# mcp_cli/gmail_client.py
import base64
import os.path
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import SCOPES, ensure_dir_exists  # Use relative import


def get_gmail_service(credentials_path, token_path):
    ensure_dir_exists(credentials_path)
    ensure_dir_exists(token_path)
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Failed to refresh token: {e}. Please re-authenticate.")
                creds = None  # Force re-authentication
        else:
            if not os.path.exists(credentials_path):
                print(f"ERROR: Google API credentials file not found at {credentials_path}")
                print(
                    "Please download it from Google Cloud Console and place it there or specify path with --credentials."
                )
                return None
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())
    try:
        service = build("gmail", "v1", credentials=creds)
        return service
    except HttpError as error:
        print(f"An API error occurred: {error}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during service build: {e}")
        return None


# --- Add other Gmail functions here ---
# get_unread_emails(service, max_results=10)
# get_email_details(service, message_id)
# delete_message(service, message_id)
# get_label_ids_by_name(service, label_names)
# modify_message_labels(service, message_id, add_label_ids, remove_label_ids)
# create_draft(service, to, subject, message_text, thread_id=None)
# (Copy these from the previous example, making sure to handle HttpError)
# For brevity, I'll omit them here but you need to include them.
# Example for one:
def get_unread_emails(service, max_results=10, query="is:unread"):
    try:
        results = (
            service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        )
        messages = results.get("messages", [])
        return messages
    except HttpError as error:
        print(f"An error occurred while fetching messages: {error}")
        return []


def get_email_details(service, message_id):
    try:
        # Use format='full' to get headers including threadId easily
        message = (
            service.users().messages().get(userId="me", id=message_id, format="full").execute()
        )

        email_data = {
            "id": message_id,
            "snippet": message.get("snippet"),
            "threadId": message.get("threadId"),
        }

        # Parse headers from message['payload']['headers']
        headers = message.get("payload", {}).get("headers", [])
        for header in headers:
            email_data[header["name"].lower()] = header["value"]

        # Find body parts
        parts = message.get("payload", {}).get("parts", [])
        if not parts and message.get("payload", {}).get("body", {}).get(
            "data"
        ):  # Single part, not multipart
            parts = [message.get("payload")]

        for part in parts:
            mime_type = part.get("mimeType")
            body_data = part.get("body", {}).get("data")
            if not body_data:  # For nested parts
                nested_parts = part.get("parts", [])
                for nested_part in nested_parts:
                    nested_mime_type = nested_part.get("mimeType")
                    nested_body_data = nested_part.get("body", {}).get("data")
                    if nested_body_data:
                        if nested_mime_type == "text/plain" and "body_plain" not in email_data:
                            email_data["body_plain"] = base64.urlsafe_b64decode(
                                nested_body_data
                            ).decode("utf-8", errors="replace")
                        elif nested_mime_type == "text/html" and "body_html" not in email_data:
                            email_data["body_html"] = base64.urlsafe_b64decode(
                                nested_body_data
                            ).decode("utf-8", errors="replace")
            elif body_data:
                if mime_type == "text/plain":
                    email_data["body_plain"] = base64.urlsafe_b64decode(body_data).decode(
                        "utf-8", errors="replace"
                    )
                elif mime_type == "text/html":
                    email_data["body_html"] = base64.urlsafe_b64decode(body_data).decode(
                        "utf-8", errors="replace"
                    )

        # Fallback if only HTML or only Plain is found but user wants the other one
        if "body_plain" not in email_data and "body_html" in email_data:
            # Basic HTML to text conversion (can be improved with libraries like beautifulsoup4 and html2text)
            # For simplicity, just using the snippet if plain text is missing and HTML is complex
            # You might want to add `poetry add beautifulsoup4 html2text` for better conversion
            email_data["body_plain"] = email_data.get("snippet", "")

        return email_data
    except HttpError as error:
        print(f"An error occurred while fetching email {message_id}: {error}")
        return None
    except Exception as e:
        print(f"Unexpected error parsing email {message_id}: {e}")
        return None


def delete_message(service, message_id):
    try:
        service.users().messages().trash(userId="me", id=message_id).execute()
        print(f"Message with id: {message_id} trashed successfully.")
    except HttpError as error:
        print(f"An error occurred while trashing message {message_id}: {error}")


def modify_message_labels(service, message_id, add_label_ids, remove_label_ids):
    try:
        body = {"addLabelIds": add_label_ids, "removeLabelIds": remove_label_ids}
        service.users().messages().modify(userId="me", id=message_id, body=body).execute()
        # print(f"Modified labels for message {message_id}: Added {add_label_ids}, Removed {remove_label_ids}")
    except HttpError as error:
        print(f"An error occurred while modifying labels for message {message_id}: {error}")


def get_label_ids_by_name(service, label_names_to_find):
    if not label_names_to_find:
        return []
    try:
        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])
        label_map = {label["name"].lower(): label["id"] for label in labels}

        ids_to_return = []
        for name in label_names_to_find:
            name_lower = name.lower()
            if name_lower in label_map:
                ids_to_return.append(label_map[name_lower])
            else:
                print(
                    f"Warning: Label '{name}' not found. It will not be applied. You may need to create it in Gmail first."
                )
        return ids_to_return
    except HttpError as error:
        print(f"An error occurred while fetching labels: {error}")
        return []


def create_draft(
    service, to, subject, message_text, thread_id=None, in_reply_to=None, references=None
):
    try:
        message = MIMEText(message_text)
        message["to"] = to
        message["subject"] = subject
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = references

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft_body = {"message": {"raw": raw_message}}
        if thread_id:
            draft_body["message"]["threadId"] = thread_id

        draft = service.users().drafts().create(userId="me", body=draft_body).execute()
        print(f"Draft created successfully. Draft ID: {draft['id']}")
        return draft
    except HttpError as error:
        print(f"An error occurred while creating draft: {error}")
        return None
