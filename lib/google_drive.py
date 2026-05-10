"""
Google Drive and Docs read helpers.

Auth uses a service account JSON loaded from the GOOGLE_SERVICE_ACCOUNT_JSON
environment variable. Amy shares each doc and folder with the service
account email once during setup.

Public functions:
    read_doc(doc_id) -> str
    list_files_in_folder(folder_id) -> list[dict]
    download_file(file_id) -> bytes or str
"""

import io
import json
import os
import logging

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]


def _get_credentials():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not set")

    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON: {exc}")

    from google.oauth2 import service_account

    return service_account.Credentials.from_service_account_info(
        info,
        scopes=SCOPES,
    )


def _docs_service():
    from googleapiclient.discovery import build

    creds = _get_credentials()
    return build("docs", "v1", credentials=creds, cache_discovery=False)


def _drive_service():
    from googleapiclient.discovery import build

    creds = _get_credentials()
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _flatten_doc_text(doc):
    """Walk a Google Docs JSON body and concatenate runs into plain text."""
    parts = []
    body = doc.get("body", {})
    for element in body.get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for run in paragraph.get("elements", []):
            text_run = run.get("textRun")
            if text_run and text_run.get("content"):
                parts.append(text_run["content"])
    return "".join(parts)


def read_doc(doc_id: str) -> str:
    """Read a Google Doc as plain text."""
    service = _docs_service()
    doc = service.documents().get(documentId=doc_id).execute()
    return _flatten_doc_text(doc)


def list_files_in_folder(folder_id: str):
    """
    Return file metadata dicts inside a Drive folder.

    Sorted by modifiedTime descending so the newest file is first.
    """
    service = _drive_service()
    query = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType, modifiedTime, size)",
        orderBy="modifiedTime desc",
        pageSize=50,
    ).execute()
    return results.get("files", [])


def download_file(file_id: str):
    """
    Download a Drive file.

    Returns bytes for binary files (PDF, images, sheets exported as xlsx).
    Returns str for native Google Docs which export as text.
    Returns None on error.
    """
    from googleapiclient.http import MediaIoBaseDownload

    service = _drive_service()

    # Look up metadata first to handle Google-native files
    meta = service.files().get(
        fileId=file_id,
        fields="id, name, mimeType",
    ).execute()
    mime = meta.get("mimeType", "")

    buf = io.BytesIO()

    if mime == "application/vnd.google-apps.document":
        request = service.files().export_media(
            fileId=file_id,
            mimeType="text/plain",
        )
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue().decode("utf-8", errors="replace")

    if mime == "application/vnd.google-apps.spreadsheet":
        request = service.files().export_media(
            fileId=file_id,
            mimeType="text/csv",
        )
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue().decode("utf-8", errors="replace")

    # Binary download for everything else (PDF, xlsx, images)
    request = service.files().get_media(fileId=file_id)
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()
