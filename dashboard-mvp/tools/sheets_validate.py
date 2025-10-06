#!/usr/bin/env python3
"""Validate Google Sheets data against local schemas."""
import datetime as dt
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
SAMPLE_ROWS = 200

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def load_schema(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def get_service():
    creds = service_account.Credentials.from_service_account_file(SA_PATH, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def get_values(service, sheet: str) -> list[list[str]]:
    rng = f"{sheet}!A1:ZZ{SAMPLE_ROWS}"
    resp = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=rng).execute()
    return resp.get("values", [])


def parse_date(value: str) -> bool:
    dt.date.fromisoformat(value)
    return True


def parse_datetime(value: str) -> bool:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt.datetime.fromisoformat(value)
    return True


def is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def type_ok(value: str, expected: str) -> bool:
    if value is None or value == "":
        return True

    if expected == "string":
        return True
    if expected == "int":
        try:
            int(float(value))
            return True
        except (TypeError, ValueError):
            return False
    if expected == "number":
        return is_number(value)
    if expected == "date":
        try:
            return parse_date(value)
        except ValueError:
            return False
    if expected == "datetime":
        try:
            return parse_datetime(value)
        except ValueError:
            return False
    return True


def validate():
    if not SPREADSHEET_ID or not SA_PATH:
        print("Please set SPREADSHEET_ID and GOOGLE_SA_JSON_PATH in .env")
        sys.exit(1)

    service = get_service()
    overall_ok = True

    for schema_path in sorted(SCHEMAS_DIR.glob("*.yaml")):
        schema = load_schema(schema_path)
        title = schema["sheet"]
        columns = schema["columns"]
        expected_header = [col["name"] for col in columns]
        required_fields = {col["name"] for col in columns if col.get("required")}
        type_map = {col["name"]: col["type"] for col in columns}

        data = get_values(service, title)
        if not data:
            print(f"[WARN] Sheet '{title}' empty")
            continue

        header = data[0]
        if header != expected_header:
            print(f"[FAIL] Header mismatch in '{title}'")
            print(" expected:", expected_header)
            print(" actual  :", header)
            overall_ok = False
            continue

        for idx, row in enumerate(data[1:], start=2):
            row_dict = {name: (row[i] if i < len(row) else "") for i, name in enumerate(header)}

            for field in required_fields:
                if row_dict.get(field, "") == "":
                    print(f"[FAIL] {title} R{idx}: required '{field}' is empty")
                    overall_ok = False

            for field, expected_type in type_map.items():
                value = row_dict.get(field, "")
                if not type_ok(value, expected_type):
                    print(f"[FAIL] {title} R{idx}: '{field}'='{value}' not {expected_type}")
                    overall_ok = False

    if overall_ok:
        print("[OK] Validation passed")
    else:
        sys.exit(2)


if __name__ == "__main__":
    validate()