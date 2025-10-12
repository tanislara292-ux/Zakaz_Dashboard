#!/usr/bin/env python3
"""Synchronise Google Sheets structure with local schemas."""
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()
ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = ROOT / "schemas" / "sheets"

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SA_PATH = os.getenv("GOOGLE_SA_JSON_PATH")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def load_schema(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def get_service():
    creds = service_account.Credentials.from_service_account_file(SA_PATH, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def list_sheets(service):
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    return [sheet["properties"]["title"] for sheet in meta.get("sheets", [])]


def add_sheet_if_missing(service, title: str):
    if title in list_sheets(service):
        return
    body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
    service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body).execute()


def to_column_letter(index: int) -> str:
    """Convert 0-based index to column letters (A, B, ..., AA)."""
    result = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def set_header_row(service, title: str, columns: list[dict]):
    header = [[col["name"] for col in columns]]
    end_col = to_column_letter(len(columns) - 1)
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{title}!A1:{end_col}1",
        valueInputOption="RAW",
        body={"values": header},
    ).execute()


def ensure():
    if not SPREADSHEET_ID or not SA_PATH:
        print("Please set SPREADSHEET_ID and GOOGLE_SA_JSON_PATH in .env")
        sys.exit(1)

    service = get_service()

    for schema_path in sorted(SCHEMAS_DIR.glob("*.yaml")):
        schema = load_schema(schema_path)
        title = schema["sheet"]
        columns = schema["columns"]
        add_sheet_if_missing(service, title)
        set_header_row(service, title, columns)
        print(f"[OK] Sheet '{title}' aligned.")


if __name__ == "__main__":
    ensure()