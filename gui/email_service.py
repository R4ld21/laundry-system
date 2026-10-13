"""Gmail SMTP service for sending completion notifications."""

import json
import smtplib
from email.message import EmailMessage
from pathlib import Path

from validators import (
    format_currency,
    format_order_date,
    format_order_id,
    format_weight,
)
from config import RATE_PER_KG


# ... paste the entire GmailService class here (no changes)