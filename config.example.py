"""Application-wide constants, colors, and database settings."""

import os
from decimal import Decimal
from pathlib import Path

APP_TITLE = "Laundry Management System"
RATE_PER_KG = Decimal("50.00")
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

STATUS_PENDING = "Pending"
STATUS_COMPLETED = "Completed"
STATUSES = [STATUS_PENDING, STATUS_COMPLETED]

STATUS_COLORS = {
    STATUS_PENDING: "#E8890C",
    STATUS_COMPLETED: "#8590A0",
}

COLORS = {
    "main_bg": ("#F0F4F7", "#10161C"),
    "card": ("#FFFFFF", "#1B232C"),
    "row": ("#F5F8FA", "#232D38"),
    "row_done": ("#EDF0F3", "#1E2630"),
    "border": ("#D5DEE5", "#2C3948"),
    "text": ("#16242D", "#E8EFF4"),
    "muted": ("#586A77", "#9BAAB6"),
    "primary": ("#0B6E8A", "#1D8BAA"),
    "primary_hover": ("#09596F", "#17718B"),
    "secondary": ("#D7E0E7", "#2C3948"),
    "secondary_hover": ("#C5D1DB", "#38485A"),
    "success": "#1E9E5A",
    "danger": "#D64545",
    "sidebar_bg": ("#0B3C4D", "#0A2631"),
    "sidebar_card": ("#125268", "#10384A"),
    "sidebar_text": "#F2F8FA",
    "sidebar_muted": "#9FC3CF",
    "sidebar_button": "#1D8BAA",
    "sidebar_button_hover": "#17718B",
    "sidebar_outline": "#3E7F94",
    "rate_card": "#E6F4F8",
    "rate_text": "#0B3C4D",
    "rate_muted": "#3F6B7A",
}

FONT_FAMILY = "Segoe UI"

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "gmail_config.json"
RECEIPTS_DIR = BASE_DIR / "receipts"

# MySQL connection settings.
# You can override with environment variables if you prefer.
DB_HOST = os.environ.get("LAUNDRY_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("LAUNDRY_DB_PORT", "3306"))
DB_USER = os.environ.get("LAUNDRY_DB_USER", "root")
DB_PASSWORD = os.environ.get("LAUNDRY_DB_PASSWORD", "password")
DB_NAME = os.environ.get("LAUNDRY_DB_NAME", "LaundryDB")