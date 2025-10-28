#!/usr/bin/env python3
"""
Static validation helper for ClickHouse DDLs.

Detects:
  * Views referencing columns that are missing from their source tables.
  * Non-deterministic expressions (today()/now()) inside PARTITION BY clauses.

The script is intentionally lightweight so it can run inside CI without
requiring a ClickHouse instance.
"""
from __future__ import annotations

import re
from pathlib import Path

DDL_DIR = Path("dashboard-mvp/infra/clickhouse")
DDL_FILES = [
    "bootstrap_schema.sql",
    "bootstrap_all.sql",
    "init.sql",
    "init_qtickets_sheets.sql",
    "init_integrations.sql",
    "init_mail.sql",
    "migrations/2025-qtickets-api.sql",
    "migrations/2025-qtickets-api-final.sql",
]


def read_file(path: Path) -> str:
    encodings = ("utf-8", "utf-8-sig", "cp1251", "latin-1")
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot read {path} with supported encodings")


CREATE_TABLE_PATTERN = re.compile(
    r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([\w\.]+)\s*\((.*?)\)\s*ENGINE",
    re.IGNORECASE | re.DOTALL,
)
COLUMN_PATTERN = re.compile(r"^[\s,]*([`\"]?[\w]+[`\"]?)\s+[A-Z]", re.MULTILINE | re.IGNORECASE)
VIEW_PATTERN = re.compile(
    r"CREATE\s+OR\s+REPLACE\s+VIEW\s+([\w\.]+)\s+AS\s+(.*?);",
    re.IGNORECASE | re.DOTALL,
)
ALIAS_PATTERN = re.compile(r"(?:FROM|JOIN)\s+([\w\.]+)(?:\s+AS)?\s+([\w]+)", re.IGNORECASE)
COLUMN_REF_PATTERN = re.compile(r"([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)")


def normalise(name: str) -> str:
    return name.strip().strip("`\"")


def extract_tables(sql: str) -> dict[str, set[str]]:
    tables: dict[str, set[str]] = {}
    for match in CREATE_TABLE_PATTERN.finditer(sql):
        table = match.group(1).strip()
        columns_block = match.group(2)
        columns: set[str] = set()
        for col_match in COLUMN_PATTERN.finditer(columns_block):
            col = normalise(col_match.group(1))
            if col and not col.startswith("--"):
                columns.add(col)
        tables[table] = columns
    return tables


def extract_view_issues(sql: str, tables: dict[str, set[str]]) -> list[str]:
    issues: list[str] = []
    for match in VIEW_PATTERN.finditer(sql):
        view = match.group(1)
        body = match.group(2)
        aliases: dict[str, str] = {}
        for alias_match in ALIAS_PATTERN.finditer(body):
            source, alias = alias_match.groups()
            if source in tables:
                aliases[alias] = source
        for col_match in COLUMN_REF_PATTERN.finditer(body):
            alias, column = col_match.groups()
            if alias not in aliases:
                continue
            table = aliases[alias]
            if column not in tables.get(table, set()):
                issues.append(
                    f"View {view} references missing column {alias}.{column} (table {table})"
                )
    return issues


def find_nondeterministic_partitions(sql: str) -> list[str]:
    issues: list[str] = []
    patterns = (
        r"PARTITION\s+BY[^;]*\btoday\(\)",
        r"PARTITION\s+BY[^;]*\bnow\(\)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, sql, flags=re.IGNORECASE | re.DOTALL):
            snippet = sql[match.start():match.start() + 120].replace("\n", " ")
            if "tuple()" in snippet.lower():
                continue
            issues.append(f"Non-deterministic PARTITION BY expression: {snippet.strip()}")
    return issues


def check_schema_consistency(tables_by_file: dict[str, dict[str, set[str]]]) -> list[str]:
    """Check that the same table has identical column sets across all files."""
    issues: list[str] = []

    # Collect all tables across all files
    all_tables: dict[str, dict[str, set[str]]] = {}
    for file_name, tables in tables_by_file.items():
        for table_name, columns in tables.items():
            if table_name not in all_tables:
                all_tables[table_name] = {}
            all_tables[table_name][file_name] = columns

    # Check for schema conflicts
    for table_name, file_columns in all_tables.items():
        if len(file_columns) <= 1:
            continue  # Table appears in only one file, no conflicts

        # Compare all schemas
        schema_sets = [frozenset(columns) for columns in file_columns.values()]
        unique_schemas = set(schema_sets)

        if len(unique_schemas) > 1:
            # Schema conflict detected
            issues.append(f"Table '{table_name}' has conflicting schemas across files:")
            for file_name, columns in file_columns.items():
                schema_str = ", ".join(sorted(columns))
                issues.append(f"  - {file_name}: {schema_str}")
            issues.append("")  # Empty line for readability

    return issues


def main() -> int:
    tables: dict[str, set[str]] = {}
    tables_by_file: dict[str, dict[str, set[str]]] = {}
    combined_sql = ""

    for file in DDL_FILES:
        path = DDL_DIR / file
        content = read_file(path)
        combined_sql += content + "\n"
        file_tables = extract_tables(content)
        tables.update(file_tables)
        tables_by_file[file] = file_tables

    issues = extract_view_issues(combined_sql, tables)
    issues.extend(find_nondeterministic_partitions(combined_sql))
    issues.extend(check_schema_consistency(tables_by_file))

    if issues:
        print("Schema validation found potential issues:")
        for issue in sorted(set(issues)):
            print(f" - {issue}")
        return 1

    print("Schema validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
