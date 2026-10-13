"""Input validation and formatting helpers."""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from config import DATE_FORMAT, RATE_PER_KG


def format_currency(amount):
    return f"\u20b1{float(amount):,.2f}"


def format_weight(value):
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return f"{text} kg"


def format_order_id(order_id):
    return f"#{int(order_id):03d}"


def format_order_date(value):
    try:
        if isinstance(value, datetime):
            moment = value
        else:
            moment = datetime.strptime(str(value), DATE_FORMAT)
        hour = moment.hour % 12 or 12
        suffix = "AM" if moment.hour < 12 else "PM"
        return f"{moment.strftime('%b')} {moment.day}, {hour}:{moment.minute:02d} {suffix}"
    except (TypeError, ValueError):
        return str(value)


def validate_name(raw):
    name = " ".join((raw or "").split())
    if not name:
        raise ValueError("Please enter the customer's name.")
    if len(name) < 2 or not any(ch.isalpha() for ch in name):
        raise ValueError("Please enter a valid customer name.")
    if len(name) > 80:
        raise ValueError("Customer name must be 80 characters or fewer.")
    return name


def validate_email(raw):
    email = (raw or "").strip().lower()
    if not email:
        raise ValueError("Please enter the customer's Gmail address.")
    if len(email) > 254:
        raise ValueError("Email address is too long.")
    pattern = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
    if not re.fullmatch(pattern, email):
        raise ValueError("Please enter a valid Gmail address, for example customer@gmail.com.")
    if not email.endswith("@gmail.com"):
        raise ValueError("This field is for Gmail addresses ending in @gmail.com.")
    return email


def parse_weight(raw):
    text = (raw or "").strip()
    text = re.sub(r"\s*kgs?\.?$", "", text, flags=re.IGNORECASE)

    if not text:
        raise ValueError("Please enter the laundry weight in kilograms.")

    if not re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)", text):
        raise ValueError("Weight must be a positive number such as 2.5.")

    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("Weight must be a valid number.") from exc

    if value <= 0:
        raise ValueError("Weight must be greater than zero.")
    if value > Decimal("50"):
        raise ValueError("Weight cannot exceed 50 kg per order.")

    value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if value <= 0:
        raise ValueError("Weight must be greater than zero.")
    return value


def calculate_total(weight):
    return (Decimal(weight) * RATE_PER_KG).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )