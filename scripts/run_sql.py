"""Execute a SQL Server script file batch by batch.

Supports UTF-8 (with/without BOM) and GBK files, splits on lines containing
only GO, and prints server PRINT/error messages as UTF-8 text.

Examples:
    py scripts/run_sql.py sql/migration.sql
    py scripts/run_sql.py sql/regression.sql --database PetCareDB
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pyodbc

GO_RE = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)


def read_sql(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Cannot decode {path} as UTF-8 or GBK")


def split_batches(sql: str) -> list[str]:
    return [part.strip() for part in GO_RE.split(sql) if part.strip()]


def build_connection(args: argparse.Namespace) -> pyodbc.Connection:
    parts = [
        f"DRIVER={{{args.driver}}}",
        f"SERVER={args.server}",
        f"DATABASE={args.database}",
        "Encrypt=yes",
        "TrustServerCertificate=yes",
    ]
    if args.trusted:
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={args.user}")
        parts.append(f"PWD={args.password}")
    return pyodbc.connect(";".join(parts) + ";", autocommit=True, timeout=args.timeout)


def drain(cursor: pyodbc.Cursor) -> None:
    while True:
        if cursor.description is not None:
            cursor.fetchall()
        if not cursor.nextset():
            break


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    parser.add_argument("--server", default="localhost")
    parser.add_argument("--database", default="PetCareDB")
    parser.add_argument("--driver", default="ODBC Driver 18 for SQL Server")
    parser.add_argument("--trusted", action="store_true", default=True)
    parser.add_argument("--user")
    parser.add_argument("--password")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    sql = read_sql(args.file)
    batches = split_batches(sql)
    lines: list[str] = []

    def emit(text: str = "") -> None:
        print(text)
        lines.append(text)

    emit(f"== {args.file} ({len(batches)} batches) ==")
    try:
        conn = build_connection(args)
    except pyodbc.Error as exc:
        emit(f"CONNECT ERROR: {exc}")
        return 2

    cursor = conn.cursor()
    try:
        for index, batch in enumerate(batches, start=1):
            try:
                cursor.execute(batch)
                drain(cursor)
                for message in cursor.messages:
                    text = message[1] if len(message) > 1 else str(message)
                    emit(str(text).rstrip())
                emit(f"[batch {index}] OK")
            except pyodbc.Error as exc:
                emit(f"[batch {index}] ERROR: {exc}")
                for message in cursor.messages:
                    text = message[1] if len(message) > 1 else str(message)
                    emit(str(text).rstrip())
                return 1
    finally:
        cursor.close()
        conn.close()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
