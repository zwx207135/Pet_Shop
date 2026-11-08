"""PetCare data access layer (DAO).

Members A's side of the A/B contract.  The service layer (member B) passes a
connection into every DAO method; only ``Database.transaction`` commits.
"""

from .config import ConfigError, DbConfig
from .database import Database
from .employee_dao import EmployeeDAO
from .errors import DAOError, ErrorCode, TransactionStateError
from .inventory_dao import InventoryDAO
from .member_dao import MemberDAO
from .models import OrderItemInput, Page
from .order_dao import OrderDAO
from .product_dao import ProductDAO
from .report_dao import ReportDAO

__all__ = [
    "ConfigError",
    "DAOError",
    "Database",
    "DbConfig",
    "EmployeeDAO",
    "ErrorCode",
    "InventoryDAO",
    "MemberDAO",
    "OrderDAO",
    "OrderItemInput",
    "Page",
    "ProductDAO",
    "ReportDAO",
    "TransactionStateError",
]
