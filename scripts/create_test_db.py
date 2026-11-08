"""Recreate PetCareDB_test from the current PetCareDB for the DAO test suite.

Usage:
    py scripts/create_test_db.py
"""

from __future__ import annotations

import argparse
import os
import sys

import pyodbc

_DRIVER_PREFERENCES = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "ODBC Driver 13 for SQL Server",
    "SQL Server",
)


def _pick_driver() -> str:
    """Choose an installed SQL Server ODBC driver (18 > 17 > 13 > legacy)."""
    installed = set(pyodbc.drivers())
    for name in _DRIVER_PREFERENCES:
        if name in installed:
            return name
    return _DRIVER_PREFERENCES[0]


MASTER = (
    "DRIVER={" + _pick_driver() + "};SERVER=localhost;DATABASE=master;"
    "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
)
TABLES = (
    "Product",
    "Inventory",
    "InventoryLog",
    "Member",
    "Employee",
    "Orders",
    "OrderDetail",
    "PetService",
    "ServiceAppointment",
)


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="PetCareDB")
    parser.add_argument("--target", default="PetCareDB_test")
    args = parser.parse_args()

    conn = pyodbc.connect(MASTER, autocommit=True)
    cursor = conn.cursor()

    data_path = cursor.execute(
        "SELECT CAST(SERVERPROPERTY('InstanceDefaultDataPath') AS NVARCHAR(400));"
    ).fetchone()[0]
    backup = os.path.join(data_path, f"{args.target}.bak")
    data_file = os.path.join(data_path, f"{args.target}.mdf")
    log_file = os.path.join(data_path, f"{args.target}_log.ldf")

    if cursor.execute("SELECT DB_ID(?);", [args.target]).fetchone()[0] is not None:
        cursor.execute(
            f"ALTER DATABASE [{args.target}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;"
        )
        cursor.execute(f"DROP DATABASE [{args.target}];")

    cursor.execute(
        f"BACKUP DATABASE [{args.source}] TO DISK = {literal(backup)} "
        "WITH INIT, COPY_ONLY;"
    )
    while cursor.nextset():
        pass

    cursor.execute(f"RESTORE FILELISTONLY FROM DISK = {literal(backup)};")
    files = cursor.fetchall()
    data_logical = next(row[0] for row in files if str(row[2]).upper() == "D")
    log_logical = next(row[0] for row in files if str(row[2]).upper() == "L")
    while cursor.nextset():
        pass

    cursor.execute(
        f"RESTORE DATABASE [{args.target}] FROM DISK = {literal(backup)} "
        f"WITH MOVE N'{data_logical}' TO {literal(data_file)}, "
        f"MOVE N'{log_logical}' TO {literal(log_file)}, "
        "RECOVERY, REPLACE;"
    )
    while cursor.nextset():
        pass

    print(f"created {args.target} from {args.source}")
    for table in TABLES:
        count = cursor.execute(
            f"SELECT COUNT(*) FROM [{args.target}].dbo.[{table}];"
        ).fetchone()[0]
        print(f"  {table}: {count}")

    cursor.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
