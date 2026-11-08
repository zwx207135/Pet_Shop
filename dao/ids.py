"""Primary-key generation backed by SQL Server sequences."""

from __future__ import annotations

from dataclasses import dataclass

import pyodbc
from pyodbc import Connection

from .errors import translate_pyodbc_error
from .utils import require_transaction


@dataclass(frozen=True)
class IdSpec:
    sequence: str
    prefix: str
    width: int


ID_SPECS: dict[str, IdSpec] = {
    "product": IdSpec("dbo.SEQ_Product", "P", 7),
    "inventory": IdSpec("dbo.SEQ_Inventory", "I", 7),
    "inventory_log": IdSpec("dbo.SEQ_InventoryLog", "L", 9),
    "member": IdSpec("dbo.SEQ_Member", "M", 7),
    "employee": IdSpec("dbo.SEQ_Employee", "E", 7),
    "order": IdSpec("dbo.SEQ_Order", "O", 11),
    "order_detail": IdSpec("dbo.SEQ_OrderDetail", "D", 9),
    "pet_service": IdSpec("dbo.SEQ_PetService", "SV", 6),
    "service_appointment": IdSpec("dbo.SEQ_ServiceAppointment", "A", 9),
}


def next_id(conn: Connection, kind: str) -> str:
    try:
        spec = ID_SPECS[kind]
    except KeyError:
        raise ValueError(f"Unknown id kind: {kind}") from None
    require_transaction(conn)
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT NEXT VALUE FOR {spec.sequence};")
        value = cursor.fetchone()[0]
    except pyodbc.Error as exc:
        raise translate_pyodbc_error(exc) from exc
    finally:
        cursor.close()
    return f"{spec.prefix}{int(value):0{spec.width}d}"
