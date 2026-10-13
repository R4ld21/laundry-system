import json
import os
import re
import smtplib
import mysql.connector
from mysql.connector import Error as MySQLError
import threading
import tkinter as tk
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from email.message import EmailMessage
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk


APP_TITLE = "Laundry Management System"
RATE_PER_KG = Decimal("50.00")
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
# Simplified staff workflow:
#   Pending -> Completed
# The staff does not choose intermediate statuses.
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
    "menu": ("#E6ECF1", "#2C3948"),
    "menu_button": ("#D3DDE5", "#38485A"),
    "menu_hover": ("#C2CFDA", "#46586D"),
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
# SQL Server connection settings (create the database first with laundry_schema.sql in SSMS).
# Each value can be overridden with an environment variable, so nothing secret lives in the code.
DB_HOST = os.environ.get("LAUNDRY_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("LAUNDRY_DB_PORT", "3306"))
DB_USER = os.environ.get("LAUNDRY_DB_USER", "root")
DB_PASSWORD = os.environ.get("LAUNDRY_DB_PASSWORD", "Gerald060712")
DB_NAME = os.environ.get("LAUNDRY_DB_NAME", "LaundryDB")
CONFIG_PATH = BASE_DIR / "gmail_config.json"
RECEIPTS_DIR = BASE_DIR / "receipts"    


def format_currency(amount):
    return f"₱{float(amount):,.2f}"


def format_weight(value):
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return f"{text} kg"


def format_order_id(order_id):
    return f"#{int(order_id):03d}"


def format_order_date(value):
    try:
        moment = datetime.strptime(value, DATE_FORMAT)
        hour = moment.hour % 12 or 12
        suffix = "AM" if moment.hour < 12 else "PM"
        return f"{moment.strftime('%b')} {moment.day}, {hour}:{moment.minute:02d} {suffix}"
    except (TypeError, ValueError):
        return str(value)


def get_next_status(status):
    try:
        index = STATUSES.index(status)
    except ValueError:
        return None
    return STATUSES[index + 1] if index + 1 < len(STATUSES) else None


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

    value = value.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    if value <= 0:
        raise ValueError("Weight must be greater than zero.")

    return value


def calculate_total(weight):
    return (
        Decimal(weight) * RATE_PER_KG
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

class LaundryDatabase:
    """All MySQL operations (through mysql-connector-python)."""

    ORDER_SELECT = """
        SELECT
            o.OrderId    AS id,
            c.Name       AS name,
            c.Email      AS email,
            o.WeightKg   AS weight_kg,
            o.TotalPrice AS total_price,
            o.Status     AS status,
            o.ReceivedAt AS date_received
        FROM Orders AS o
        INNER JOIN Customers AS c
            ON c.CustomerId = o.CustomerId
    """

    def __init__(self):
        self.conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            autocommit=True,
        )

    @staticmethod
    def _clean(value):
        if isinstance(value, datetime):
            return value.strftime(DATE_FORMAT)
        return value

    def _rows(self, cursor):
        columns = [col[0] for col in cursor.description]
        return [
            dict(zip(columns, map(self._clean, row)))
            for row in cursor.fetchall()
        ]

    def query_all(self, sql, params=()):
        cursor = self.conn.cursor()
        try:
            cursor.execute(sql, params)
            return self._rows(cursor)
        finally:
            cursor.close()

    def query_one(self, sql, params=()):
        rows = self.query_all(sql, params)
        return rows[0] if rows else None

    @contextmanager
    def transaction(self):
        self.conn.autocommit = False
        cursor = self.conn.cursor()
        try:
            yield cursor
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        finally:
            cursor.close()
            self.conn.autocommit = True

    def save_customer(self, cursor, name, email):
        cursor.execute(
            "SELECT CustomerId FROM Customers "
            "WHERE LOWER(IFNULL(Email,'')) = LOWER(%s) LIMIT 1",
            (email,),
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                "UPDATE Customers SET Name = %s WHERE CustomerId = %s",
                (name, existing[0]),
            )
            return existing[0]

        cursor.execute(
            "INSERT INTO Customers (Name, Email) VALUES (%s, %s)",
            (name, email),
        )
        return cursor.lastrowid

    def add_order(self, name, email, weight, total, status, date_received):
        received = datetime.strptime(date_received, DATE_FORMAT)

        with self.transaction() as cursor:
            customer_id = self.save_customer(cursor, name, email)
            cursor.execute(
                """
                INSERT INTO Orders
                    (CustomerId, WeightKg, RatePerKg, TotalPrice, Status, ReceivedAt)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    customer_id,
                    Decimal(weight),
                    RATE_PER_KG,
                    Decimal(total),
                    status,
                    received,
                ),
            )
            return cursor.lastrowid

    def get_orders(self, include_completed=True, search_term=""):
        sql = self.ORDER_SELECT
        conditions = []
        params = []

        if not include_completed:
            conditions.append("o.Status = %s")
            params.append("Pending")

        if search_term:
            like = f"%{search_term}%"
            conditions.append(
                "(c.Name LIKE %s OR c.Email LIKE %s "
                "OR CAST(o.OrderId AS CHAR) LIKE %s)"
            )
            params.extend([like, like, like])

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += """
            ORDER BY
                CASE o.Status
                    WHEN 'Pending' THEN 1
                    WHEN 'Completed' THEN 2
                    ELSE 3
                END,
                o.OrderId DESC
        """
        return self.query_all(sql, tuple(params))

    def get_statistics(self):
        totals = self.query_one(
            """
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(TotalPrice), 0) AS total_revenue
            FROM Orders
            """
        )

        counts = {status: 0 for status in STATUSES}

        for row in self.query_all(
            """
            SELECT Status AS status, COUNT(*) AS cnt
            FROM Orders
            GROUP BY Status
            """
        ):
            if row["status"] in counts:
                counts[row["status"]] = row["cnt"]

        return {
            "total_orders": totals["total_orders"],
            "total_revenue": totals["total_revenue"],
            "counts": counts,
        }

    def update_status(self, order_id, new_status):
        if new_status not in STATUSES:
            raise ValueError("Invalid order status.")

        with self.transaction() as cursor:
            cursor.execute(
                """
                UPDATE Orders
                SET Status = %s,
                    CompletedAt = CASE WHEN %s = 'Completed'
                                       THEN NOW() ELSE NULL END
                WHERE OrderId = %s
                """,
                (new_status, new_status, order_id),
            )
            updated = cursor.rowcount > 0

        return updated

    def update_order(self, order_id, name, email, weight, total):
        """Real Update: change customer + order details."""
        with self.transaction() as cursor:
            cursor.execute(
                "SELECT CustomerId FROM Orders WHERE OrderId = %s",
                (order_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False
            customer_id = row[0]

            cursor.execute(
                "UPDATE Customers SET Name = %s, Email = %s "
                "WHERE CustomerId = %s",
                (name, email, customer_id),
            )
            cursor.execute(
                "UPDATE Orders SET WeightKg = %s, TotalPrice = %s "
                "WHERE OrderId = %s",
                (Decimal(weight), Decimal(total), order_id),
            )
        return True

    def get_order(self, order_id):
        return self.query_one(
            self.ORDER_SELECT + " WHERE o.OrderId = %s",
            (order_id,),
        )

    def delete_order(self, order_id):
        with self.transaction() as cursor:
            cursor.execute(
                "DELETE FROM Orders WHERE OrderId = %s",
                (order_id,),
            )
            removed = cursor.rowcount > 0
        return removed

    def close(self):
        try:
            self.conn.close()
        except MySQLError:
            pass

class GmailService:
    """
    Sends email through Gmail SMTP.

    This uses the standard-library smtplib module and Gmail's SMTP server.
    The sender account should use a Google App Password rather than the
    normal Gmail password.
    """

    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 587

    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self.sender_email = ""
        self.app_password = ""
        self.load()

    def load(self):
        self.sender_email = ""
        self.app_password = ""

        if not self.config_path.exists():
            return

        try:
            with self.config_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            self.sender_email = str(
                data.get("sender_email", "")
            ).strip()

            self.app_password = str(
                data.get("app_password", "")
            ).replace(" ", "").strip()

        except (OSError, json.JSONDecodeError):
            pass

    def save(self, sender_email, app_password):
        sender_email = sender_email.strip().lower()
        app_password = app_password.replace(" ", "").strip()

        data = {
            "sender_email": sender_email,
            "app_password": app_password,
        }

        with self.config_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                indent=4,
            )

        self.sender_email = sender_email
        self.app_password = app_password

    def is_configured(self):
        return bool(
            self.sender_email
            and self.app_password
        )

    def send_order_completed_email(
        self,
        customer_name,
        customer_email,
        order_id,
        weight,
        total,
        date_received,
    ):
        if not self.is_configured():
            raise RuntimeError(
                "Gmail sending is not configured. "
                "Open Email Settings and enter the shop Gmail "
                "and its Google App Password."
            )

        message = EmailMessage()

        message["From"] = self.sender_email
        message["To"] = customer_email
        message["Subject"] = (
            f"Laundry Order {format_order_id(order_id)} "
            f"is Completed"
        )

        body = f"""Hello {customer_name},

Good news! Your laundry order {format_order_id(order_id)} has been completed.

Order details:
--------------------------------
Order No. : {format_order_id(order_id)}
Date      : {format_order_date(date_received)}
Weight    : {format_weight(weight)}
Rate      : {format_currency(RATE_PER_KG)} / kg
Total     : {format_currency(total)}
Status    : Completed
--------------------------------

Your laundry is ready for pickup.

Thank you for using our laundry service!

Laundry Management System
"""

        message.set_content(body)

        # Optional HTML version for a cleaner Gmail appearance.
        html = f"""
        <html>
        <body style="font-family:Arial,sans-serif;color:#16242D;">
            <h2 style="color:#0B6E8A;">Laundry Order Completed</h2>
            <p>Hello <strong>{customer_name}</strong>,</p>
            <p>
                Good news! Your laundry order
                <strong>{format_order_id(order_id)}</strong>
                has been completed.
            </p>

            <table cellpadding="7" cellspacing="0"
                   style="border-collapse:collapse;">
                <tr>
                    <td><strong>Order No.</strong></td>
                    <td>{format_order_id(order_id)}</td>
                </tr>
                <tr>
                    <td><strong>Date</strong></td>
                    <td>{format_order_date(date_received)}</td>
                </tr>
                <tr>
                    <td><strong>Weight</strong></td>
                    <td>{format_weight(weight)}</td>
                </tr>
                <tr>
                    <td><strong>Rate</strong></td>
                    <td>{format_currency(RATE_PER_KG)} / kg</td>
                </tr>
                <tr>
                    <td><strong>Total</strong></td>
                    <td><strong>{format_currency(total)}</strong></td>
                </tr>
                <tr>
                    <td><strong>Status</strong></td>
                    <td style="color:#1E9E5A;"><strong>Completed</strong></td>
                </tr>
            </table>

            <p>Your laundry is ready for pickup.</p>
            <p>Thank you for using our laundry service!</p>

            <p>
                <strong>Laundry Management System</strong>
            </p>
        </body>
        </html>
        """

        message.add_alternative(
            html,
            subtype="html",
        )

        with smtplib.SMTP(
            self.SMTP_HOST,
            self.SMTP_PORT,
            timeout=30,
        ) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()

            server.login(
                self.sender_email,
                self.app_password,
            )

            server.send_message(message)

    def send_test_email(self):
        if not self.is_configured():
            raise RuntimeError(
                "Please enter the shop Gmail and App Password first."
            )

        message = EmailMessage()
        message["From"] = self.sender_email
        message["To"] = self.sender_email
        message["Subject"] = "Laundry Management System - Test Email"

        message.set_content(
            "This is a test email from your Laundry Management System.\n\n"
            "Your Gmail notification setup is working."
        )

        with smtplib.SMTP(
            self.SMTP_HOST,
            self.SMTP_PORT,
            timeout=30,
        ) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()

            server.login(
                self.sender_email,
                self.app_password,
            )

            server.send_message(message)


class ReceiptWindow(ctk.CTkToplevel):
    """Receipt preview and save window."""

    def __init__(
        self,
        master,
        receipt_text,
        default_filename,
    ):
        super().__init__(master)

        self.receipt_text = receipt_text
        self.default_filename = default_filename

        self.title("Laundry Receipt")
        self.geometry("460x650")
        self.minsize(420, 560)

        self.transient(master)
        self.grab_set()

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="Receipt",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=20,
                weight="bold",
            ),
        ).grid(
            row=0,
            column=0,
            padx=20,
            pady=(18, 10),
            sticky="w",
        )

        self.textbox = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(
                family="Consolas",
                size=13,
            ),
            wrap="none",
        )

        self.textbox.grid(
            row=1,
            column=0,
            padx=20,
            pady=(0, 12),
            sticky="nsew",
        )

        self.textbox.insert(
            "1.0",
            receipt_text,
        )
        self.textbox.configure(
            state="disabled"
        )

        button_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )

        button_frame.grid(
            row=2,
            column=0,
            padx=20,
            pady=(0, 20),
            sticky="ew",
        )

        button_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        ctk.CTkButton(
            button_frame,
            text="Save Receipt",
            height=40,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            command=self.save_receipt,
        ).grid(
            row=0,
            column=0,
            padx=(0, 8),
            sticky="ew",
        )

        ctk.CTkButton(
            button_frame,
            text="Close",
            height=40,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["secondary_hover"],
            text_color=COLORS["text"],
            command=self.destroy,
        ).grid(
            row=0,
            column=1,
            padx=(8, 0),
            sticky="ew",
        )

    def save_receipt(self):
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save Receipt",
            initialfile=self.default_filename,
            defaultextension=".txt",
            filetypes=[
                ("Text file", "*.txt"),
                ("All files", "*.*"),
            ],
        )

        if not path:
            return

        try:
            with open(
                path,
                "w",
                encoding="utf-8",
            ) as file:
                file.write(self.receipt_text)

            messagebox.showinfo(
                "Receipt Saved",
                f"Receipt saved successfully:\n\n{path}",
                parent=self,
            )

        except OSError as exc:
            messagebox.showerror(
                "Save Error",
                f"Could not save the receipt.\n\n{exc}",
                parent=self,
            )


class EmailSettingsWindow(ctk.CTkToplevel):
    """Gmail sender configuration window."""

    def __init__(self, master, gmail_service, on_saved):
        super().__init__(master)

        self.gmail_service = gmail_service
        self.on_saved = on_saved

        self.title("Gmail Email Settings")
        self.geometry("520x450")
        self.minsize(500, 420)

        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="Gmail Notification Setup",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=21,
                weight="bold",
            ),
        ).grid(
            row=0,
            column=0,
            padx=25,
            pady=(24, 5),
            sticky="w",
        )

        ctk.CTkLabel(
            self,
            text=(
                "This is the Gmail account your laundry shop uses to send "
                "completion emails to customers."
            ),
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=12,
            ),
            text_color=COLORS["muted"],
            wraplength=450,
            justify="left",
        ).grid(
            row=1,
            column=0,
            padx=25,
            pady=(0, 18),
            sticky="w",
        )

        ctk.CTkLabel(
            self,
            text="Shop Gmail",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=12,
                weight="bold",
            ),
        ).grid(
            row=2,
            column=0,
            padx=25,
            pady=(0, 5),
            sticky="w",
        )

        self.email_entry = ctk.CTkEntry(
            self,
            height=40,
            placeholder_text="yourshop@gmail.com",
        )

        self.email_entry.grid(
            row=3,
            column=0,
            padx=25,
            pady=(0, 14),
            sticky="ew",
        )

        self.email_entry.insert(
            0,
            gmail_service.sender_email,
        )

        ctk.CTkLabel(
            self,
            text="Google App Password",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=12,
                weight="bold",
            ),
        ).grid(
            row=4,
            column=0,
            padx=25,
            pady=(0, 5),
            sticky="w",
        )

        self.password_entry = ctk.CTkEntry(
            self,
            height=40,
            placeholder_text="16-character App Password",
            show="•",
        )

        self.password_entry.grid(
            row=5,
            column=0,
            padx=25,
            pady=(0, 8),
            sticky="ew",
        )

        if gmail_service.app_password:
            self.password_entry.insert(
                0,
                gmail_service.app_password,
            )

        ctk.CTkLabel(
            self,
            text=(
                "Use a Google App Password, not your normal Gmail password. "
                "2-Step Verification must be enabled on the sender account."
            ),
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
            ),
            text_color=COLORS["muted"],
            wraplength=450,
            justify="left",
        ).grid(
            row=6,
            column=0,
            padx=25,
            pady=(0, 15),
            sticky="w",
        )

        button_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )

        button_frame.grid(
            row=7,
            column=0,
            padx=25,
            pady=(0, 20),
            sticky="ew",
        )

        button_frame.grid_columnconfigure(
            0,
            weight=1,
        )
        button_frame.grid_columnconfigure(
            1,
            weight=1,
        )

        ctk.CTkButton(
            button_frame,
            text="Cancel",
            height=40,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["secondary_hover"],
            text_color=COLORS["text"],
            command=self.destroy,
        ).grid(
            row=0,
            column=0,
            padx=(0, 6),
            sticky="ew",
        )

        ctk.CTkButton(
            button_frame,
            text="Save & Test",
            height=40,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            command=self.save_and_test,
        ).grid(
            row=0,
            column=1,
            padx=(6, 0),
            sticky="ew",
        )

    def save_and_test(self):
        email = self.email_entry.get().strip().lower()
        password = (
            self.password_entry.get()
            .replace(" ", "")
            .strip()
        )

        if not re.fullmatch(
            r"^[A-Za-z0-9._%+\-]+@gmail\.com$",
            email,
        ):
            messagebox.showerror(
                "Invalid Gmail",
                "Please enter a valid Gmail address ending in @gmail.com.",
                parent=self,
            )
            return

        if not re.fullmatch(
            r"[A-Za-z0-9]{16}",
            password,
        ):
            messagebox.showerror(
                "Invalid App Password",
                (
                    "Enter the 16-character Google App Password. "
                    "You can paste it with or without spaces."
                ),
                parent=self,
            )
            return

        try:
            self.gmail_service.save(
                email,
                password,
            )
            self.gmail_service.send_test_email()

        except Exception as exc:
            messagebox.showerror(
                "Gmail Test Failed",
                (
                    "The settings were not verified successfully.\n\n"
                    f"{exc}\n\n"
                    "Check the Gmail address, App Password, and internet connection."
                ),
                parent=self,
            )
            return

        self.on_saved()

        messagebox.showinfo(
            "Gmail Ready",
            (
                "Gmail is configured successfully.\n\n"
                "When an order reaches Completed, the system will automatically "
                "email the customer's Gmail address."
            ),
            parent=self,
        )

        self.destroy()


class Application(ctk.CTk):
    """Main LMS application."""

    def __init__(self, database, gmail_service):
        super().__init__()

        self.db = database
        self.gmail_service = gmail_service

        self.title(APP_TITLE)
        self.geometry("1240x780")
        self.minsize(1080, 650)
        self.configure(
            fg_color=COLORS["main_bg"]
        )

        self.protocol(
            "WM_DELETE_WINDOW",
            self.on_close,
        )

        self.grid_columnconfigure(
            1,
            weight=1,
        )
        self.grid_rowconfigure(
            0,
            weight=1,
        )

        self._email_sending_orders = set()

        self.build_sidebar()
        self.build_main_panel()

        self.refresh_all()
        self.name_entry.focus_set()

        self.bind(
            "<F5>",
            lambda event: self.refresh_all(),
        )

    # ============================================================
    # SIDEBAR
    # ============================================================

    def build_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self,
            width=245,
            corner_radius=0,
            fg_color=COLORS["sidebar_bg"],
        )

        self.sidebar.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(
            0,
            weight=1,
        )
        self.sidebar.grid_rowconfigure(
            7,
            weight=1,
        )

        ctk.CTkLabel(
            self.sidebar,
            text="Laundry\nManagement System",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=18,
                weight="bold",
            ),
            text_color=COLORS["sidebar_text"],
            justify="left",
            anchor="w",
        ).grid(
            row=0,
            column=0,
            padx=18,
            pady=(20, 3),
            sticky="w",
        )

        ctk.CTkLabel(
            self.sidebar,
            text="Wash-and-fold shop dashboard",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=10,
            ),
            text_color=COLORS["sidebar_muted"],
            anchor="w",
        ).grid(
            row=1,
            column=0,
            padx=18,
            pady=(0, 12),
            sticky="w",
        )

        rate_card = ctk.CTkFrame(
            self.sidebar,
            corner_radius=12,
            fg_color=COLORS["rate_card"],
        )

        rate_card.grid(
            row=2,
            column=0,
            padx=16,
            pady=(0, 12),
            sticky="ew",
        )

        ctk.CTkLabel(
            rate_card,
            text="Current price rate",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=10,
            ),
            text_color=COLORS["rate_muted"],
        ).pack(
            anchor="w",
            padx=14,
            pady=(8, 0),
        )

        ctk.CTkLabel(
            rate_card,
            text=f"{format_currency(RATE_PER_KG)} / kg",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=23,
                weight="bold",
            ),
            text_color=COLORS["rate_text"],
        ).pack(
            anchor="w",
            padx=14,
            pady=(0, 8),
        )

        ctk.CTkLabel(
            self.sidebar,
            text="Quick statistics",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=14,
                weight="bold",
            ),
            text_color=COLORS["sidebar_text"],
            anchor="w",
        ).grid(
            row=3,
            column=0,
            padx=18,
            pady=(0, 6),
            sticky="w",
        )

        stats_frame = ctk.CTkFrame(
            self.sidebar,
            fg_color="transparent",
        )

        stats_frame.grid(
            row=4,
            column=0,
            padx=16,
            sticky="ew",
        )

        stats_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        self.total_orders_value = self.create_stat_card(
            stats_frame,
            "Total orders",
            0,
        )

        self.total_revenue_value = self.create_stat_card(
            stats_frame,
            "Total revenue",
            1,
        )

        self.status_card = ctk.CTkFrame(
            self.sidebar,
            corner_radius=12,
            fg_color=COLORS["sidebar_card"],
        )

        self.status_card.grid(
            row=5,
            column=0,
            padx=16,
            pady=(4, 8),
            sticky="ew",
        )

        ctk.CTkLabel(
            self.status_card,
            text="Orders by status",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            text_color=COLORS["sidebar_muted"],
        ).grid(
            row=0,
            column=0,
            columnspan=3,
            padx=12,
            pady=(8, 3),
            sticky="w",
        )

        self.status_count_labels = {}

        for row, status in enumerate(
            STATUSES,
            start=1,
        ):
            dot = ctk.CTkFrame(
                self.status_card,
                width=9,
                height=9,
                corner_radius=5,
                fg_color=STATUS_COLORS[status],
            )

            dot.grid(
                row=row,
                column=0,
                padx=(12, 7),
                pady=2,
            )

            ctk.CTkLabel(
                self.status_card,
                text=status,
                font=ctk.CTkFont(
                    family=FONT_FAMILY,
                    size=10,
                ),
                text_color=COLORS["sidebar_text"],
            ).grid(
                row=row,
                column=1,
                sticky="w",
            )

            count_label = ctk.CTkLabel(
                self.status_card,
                text="0",
                font=ctk.CTkFont(
                    family=FONT_FAMILY,
                    size=10,
                    weight="bold",
                ),
                text_color=COLORS["sidebar_text"],
            )

            count_label.grid(
                row=row,
                column=2,
                padx=(5, 12),
                sticky="e",
            )

            self.status_count_labels[status] = count_label

        ctk.CTkButton(
            self.sidebar,
            text="Refresh dashboard",
            height=35,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            fg_color=COLORS["sidebar_button"],
            hover_color=COLORS["sidebar_button_hover"],
            command=self.refresh_all,
        ).grid(
            row=8,
            column=0,
            padx=16,
            pady=(8, 5),
            sticky="ew",
        )

        ctk.CTkButton(
            self.sidebar,
            text="Gmail Email Settings",
            height=35,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
            ),
            fg_color="transparent",
            hover_color=COLORS["sidebar_card"],
            border_width=1,
            border_color=COLORS["sidebar_outline"],
            text_color=COLORS["sidebar_text"],
            command=self.open_email_settings,
        ).grid(
            row=9,
            column=0,
            padx=16,
            pady=(0, 5),
            sticky="ew",
        )

        self.email_status_label = ctk.CTkLabel(
            self.sidebar,
            text="Email: Not configured",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=9,
            ),
            text_color="#F5C542",
            anchor="w",
        )

        self.email_status_label.grid(
            row=10,
            column=0,
            padx=18,
            pady=(0, 5),
            sticky="w",
        )

        ctk.CTkButton(
            self.sidebar,
            text="☾ / ☀  Appearance",
            height=35,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
            ),
            fg_color="transparent",
            hover_color=COLORS["sidebar_card"],
            border_width=1,
            border_color=COLORS["sidebar_outline"],
            text_color=COLORS["sidebar_text"],
            command=self.toggle_appearance,
        ).grid(
            row=11,
            column=0,
            padx=16,
            pady=(0, 14),
            sticky="ew",
        )
        ctk.CTkButton(
            self.sidebar,
            text="Logout",
            height=35,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
            ),
            fg_color="transparent",
            hover_color=COLORS["sidebar_card"],
            border_width=1,
            border_color="#B93636",
            text_color="#F5C542",
            command=self.logout,
        ).grid(
            row=12,
            column=0,
            padx=16,
            pady=(0, 5),
            sticky="ew",
        )

    def create_stat_card(self, parent, caption, row):
        card = ctk.CTkFrame(
            parent,
            corner_radius=12,
            fg_color=COLORS["sidebar_card"],
        )

        card.grid(
            row=row,
            column=0,
            sticky="ew",
            pady=(0, 6),
        )

        ctk.CTkLabel(
            card,
            text=caption,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=10,
            ),
            text_color=COLORS["sidebar_muted"],
        ).pack(
            anchor="w",
            padx=14,
            pady=(8, 0),
        )

        value = ctk.CTkLabel(
            card,
            text="0",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=21,
                weight="bold",
            ),
            text_color=COLORS["sidebar_text"],
        )

        value.pack(
            anchor="w",
            padx=14,
            pady=(0, 8),
        )

        return value

    # ============================================================
    # MAIN PANEL
    # ============================================================

    def build_main_panel(self):
        self.main = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )

        self.main.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=16,
            pady=16,
        )

        self.main.grid_columnconfigure(
            0,
            weight=1,
        )
        self.main.grid_rowconfigure(
            1,
            weight=1,
        )

        self.build_new_order_card()
        self.build_orders_card()

    def build_new_order_card(self):
        card = ctk.CTkFrame(
            self.main,
            corner_radius=14,
            fg_color=COLORS["card"],
            border_width=1,
            border_color=COLORS["border"],
        )

        card.grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(0, 14),
        )

        for column, weight in enumerate(
            [5, 4, 3]
        ):
            card.grid_columnconfigure(
                column,
                weight=weight,
            )

        ctk.CTkLabel(
            card,
            text="New Order",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=19,
                weight="bold",
            ),
            text_color=COLORS["text"],
        ).grid(
            row=0,
            column=0,
            columnspan=3,
            padx=18,
            pady=(16, 1),
            sticky="w",
        )

        ctk.CTkLabel(
            card,
            text=(
                "Enter the customer's name, Gmail, and laundry weight. "
                f"Rate: {format_currency(RATE_PER_KG)} per kilogram."
            ),
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=10,
            ),
            text_color=COLORS["muted"],
        ).grid(
            row=1,
            column=0,
            columnspan=3,
            padx=18,
            pady=(0, 10),
            sticky="w",
        )

        labels = [
            "Customer Name",
            "Gmail Address",
            "Weight (kg)",
        ]

        for column, label in enumerate(labels):
            ctk.CTkLabel(
                card,
                text=label,
                font=ctk.CTkFont(
                    family=FONT_FAMILY,
                    size=11,
                    weight="bold",
                ),
                text_color=COLORS["muted"],
            ).grid(
                row=2,
                column=column,
                padx=(
                    (18, 7)
                    if column == 0
                    else (7, 7)
                    if column == 1
                    else (7, 18)
                ),
                sticky="w",
            )

        self.name_entry = ctk.CTkEntry(
            card,
            height=39,
            placeholder_text="Juan Dela Cruz",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=12,
            ),
        )

        self.gmail_entry = ctk.CTkEntry(
            card,
            height=39,
            placeholder_text="customer@gmail.com",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=12,
            ),
        )

        self.weight_entry = ctk.CTkEntry(
            card,
            height=39,
            placeholder_text="2.5",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=12,
            ),
        )

        entries = [
            self.name_entry,
            self.gmail_entry,
            self.weight_entry,
        ]

        for column, entry in enumerate(entries):
            entry.grid(
                row=3,
                column=column,
                padx=(
                    (18, 7)
                    if column == 0
                    else (7, 7)
                    if column == 1
                    else (7, 18)
                ),
                pady=(4, 0),
                sticky="ew",
            )

            entry.bind(
                "<Return>",
                lambda event: self.add_order(),
            )

        self.weight_entry.bind(
            "<KeyRelease>",
            self.update_price_preview,
        )

        footer = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        footer.grid(
            row=4,
            column=0,
            columnspan=3,
            padx=18,
            pady=(13, 15),
            sticky="ew",
        )

        footer.grid_columnconfigure(
            0,
            weight=1,
        )

        self.price_preview = ctk.CTkLabel(
            footer,
            text=f"Estimated total: {format_currency(0)}",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=14,
                weight="bold",
            ),
            text_color=COLORS["primary"],
        )

        self.price_preview.grid(
            row=0,
            column=0,
            sticky="w",
        )

        ctk.CTkButton(
            footer,
            text="Clear",
            width=88,
            height=40,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["secondary_hover"],
            text_color=COLORS["text"],
            command=self.clear_form,
        ).grid(
            row=0,
            column=1,
            padx=(8, 8),
        )

        ctk.CTkButton(
            footer,
            text="Calculate & Add Order",
            width=220,
            height=40,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=12,
                weight="bold",
            ),
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            command=self.add_order,
        ).grid(
            row=0,
            column=2,
        )

    def build_orders_card(self):
        card = ctk.CTkFrame(
            self.main,
            corner_radius=14,
            fg_color=COLORS["card"],
            border_width=1,
            border_color=COLORS["border"],
        )

        card.grid(
            row=1,
            column=0,
            sticky="nsew",
        )

        self.orders_card = card

        top = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        top.pack(
            fill="x",
            padx=18,
            pady=(15, 7),
        )

        top.grid_columnconfigure(
            1,
            weight=1,
        )

        ctk.CTkLabel(
            top,
            text="Orders",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=19,
                weight="bold",
            ),
            text_color=COLORS["text"],
        ).grid(
            row=0,
            column=0,
            sticky="w",
        )

        self.active_count_label = ctk.CTkLabel(
            top,
            text="0 active",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color="#FFFFFF",
            fg_color=COLORS["primary"],
            corner_radius=10,
            width=72,
            height=22,
        )

        self.active_count_label.grid(
            row=0,
            column=1,
            padx=10,
            sticky="w",
        )

        self.completed_switch = ctk.CTkSwitch(
            top,
            text="Show completed",
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=10,
            ),
            text_color=COLORS["text"],
            command=self.load_orders,
        )

        self.completed_switch.select()

        self.completed_switch.grid(
            row=0,
            column=2,
            sticky="e",
        )

        # ---- Search box ----
        search_frame = ctk.CTkFrame(card, fg_color="transparent")
        search_frame.pack(fill="x", padx=18, pady=(0, 6))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.load_orders())

        ctk.CTkEntry(
            search_frame,
            textvariable=self.search_var,
            height=34,
            placeholder_text="Search by name, Gmail, or order #",
        ).pack(fill="x")


        header = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        header.pack(
            fill="x",
            padx=12,
            pady=(0, 2),
        )

        columns = [
            ("Order", 1),
            ("Customer / Gmail", 3),
            ("Weight", 1),
            ("Total", 1),
            ("Status", 2),
            ("Action", 3),
        ]

        for index, (text, weight) in enumerate(columns):
            header.grid_columnconfigure(
                index,
                weight=weight,
            )

            ctk.CTkLabel(
                header,
                text=text,
                font=ctk.CTkFont(
                    family=FONT_FAMILY,
                    size=10,
                    weight="bold",
                ),
                text_color=COLORS["muted"],
                anchor="w",
            ).grid(
                row=0,
                column=index,
                padx=6,
                pady=5,
                sticky="w",
            )

        self.orders_list = ctk.CTkScrollableFrame(
            card,
            fg_color=COLORS["card"],
            corner_radius=0,
        )

        self.orders_list.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=(0, 12),
        )

    # ============================================================
    # FORM
    # ============================================================

    def update_price_preview(self, event=None):
        try:
            weight = parse_weight(
                self.weight_entry.get()
            )
            total = calculate_total(weight)
        except ValueError:
            total = Decimal("0.00")

        self.price_preview.configure(
            text=f"Estimated total: {format_currency(total)}"
        )

    def clear_form(self):
        for entry in (
            self.name_entry,
            self.gmail_entry,
            self.weight_entry,
        ):
            entry.delete(
                0,
                tk.END,
            )

        self.update_price_preview()
        self.name_entry.focus_set()

    def add_order(self):
        try:
            name = validate_name(
                self.name_entry.get()
            )
            email = validate_email(
                self.gmail_entry.get()
            )
            weight = parse_weight(
                self.weight_entry.get()
            )
            total = calculate_total(weight)

        except ValueError as exc:
            messagebox.showerror(
                "Check Order Details",
                str(exc),
                parent=self,
            )
            return

        date_received = datetime.now().strftime(
            DATE_FORMAT
        )

        try:
            order_id = self.db.add_order(
                name=name,
                email=email,
                weight=weight,
                total=total,
                status="Pending",
                date_received=date_received,
            )

        except MySQLError as exc:
            messagebox.showerror(
                "Database Error",
                f"The order could not be saved.\n\n{exc}",
                parent=self,
            )
            return

        receipt_text = self.create_receipt_text(
            order_id=order_id,
            name=name,
            email=email,
            weight=weight,
            total=total,
            status="Pending",
            date_received=date_received,
        )

        # Automatically create a local receipt file.
        try:
            RECEIPTS_DIR.mkdir(
                parents=True,
                exist_ok=True,
            )

            receipt_path = (
                RECEIPTS_DIR
                / f"receipt_{order_id:03d}.txt"
            )

            receipt_path.write_text(
                receipt_text,
                encoding="utf-8",
            )

        except OSError:
            receipt_path = None

        self.clear_form()
        self.refresh_all()

        # Show receipt immediately after creating the order.
        window = ReceiptWindow(
            self,
            receipt_text,
            f"receipt_{order_id:03d}.txt",
        )

        window.lift()

        if receipt_path:
            self.show_toast(
                (
                    f"Order {format_order_id(order_id)} saved. "
                    "Receipt created."
                ),
                "success",
            )
        else:
            self.show_toast(
                f"Order {format_order_id(order_id)} saved.",
                "success",
            )

    def create_receipt_text(
        self,
        order_id,
        name,
        email,
        weight,
        total,
        status,
        date_received,
    ):
        width = 38

        lines = [
            "=" * width,
            "       LAUNDRY SHOP",
            "   LAUNDRY MANAGEMENT SYSTEM",
            "=" * width,
            f"Order No. : {format_order_id(order_id)}",
            f"Date      : {format_order_date(date_received)}",
            "",
            f"Customer  : {name}",
            f"Gmail     : {email}",
            "",
            "-" * width,
            f"Weight    : {format_weight(weight)}",
            f"Rate      : {format_currency(RATE_PER_KG)} / kg",
            f"TOTAL     : {format_currency(total)}",
            f"Status    : {status}",
            "-" * width,
            "",
            "Thank you for your business!",
            "",
            "Please present your order number",
            "when claiming your laundry.",
            "=" * width,
        ]

        return "\n".join(lines)

    # ============================================================
    # ORDER LIST
    # ============================================================

    def load_orders(self):
        include_completed = bool(
            self.completed_switch.get()
        )

        search_term = ""
        if hasattr(self, "search_var"):
            search_term = self.search_var.get().strip()

        try:
            orders = self.db.get_orders(
                include_completed=include_completed,
                search_term=search_term,
            )
            all_orders = self.db.get_orders(
                include_completed=True
            )

        except MySQLError as exc:
            self.show_database_error(
                "Could not load orders.",
                exc,
            )
            return

        for child in self.orders_list.winfo_children():
            child.destroy()

        active_orders = [
            order
            for order in all_orders
            if order["status"] != "Completed"
        ]

        self.active_count_label.configure(
            text=f"{len(active_orders)} active"
        )

        if not all_orders:
            self.show_empty_state(
                "No orders yet",
                "Add the first laundry order using the form above.",
            )
            return

        if not orders:
            self.show_empty_state(
                "No active orders",
                "All current orders are completed.",
            )
            return

        current_status = None

        for order in orders:
            status = order["status"]

            if (
                include_completed
                and status == "Completed"
                and current_status != "Completed"
            ):
                ctk.CTkLabel(
                    self.orders_list,
                    text="Completed Orders",
                    font=ctk.CTkFont(
                        family=FONT_FAMILY,
                        size=11,
                        weight="bold",
                    ),
                    text_color=COLORS["muted"],
                ).pack(
                    fill="x",
                    padx=4,
                    pady=(16, 4),
                )

            self.build_order_row(
                order,
                completed=(status == "Completed"),
            )

            current_status = status

    def build_order_row(self, order, completed=False):
        """Draw one order row with Completed/Remove actions."""
        order_id = order["id"]
        status = order["status"]
        status_color = STATUS_COLORS.get(
            status,
            "#8590A0",
        )

        row = ctk.CTkFrame(
            self.orders_list,
            corner_radius=10,
            fg_color=(
                COLORS["row_done"]
                if completed
                else COLORS["row"]
            ),
            border_width=1,
            border_color=COLORS["border"],
        )

        row.pack(
            fill="x",
            pady=3,
        )

        columns = [
            (0, 1),
            (1, 3),
            (2, 1),
            (3, 1),
            (4, 2),
            (5, 2),
        ]

        for index, weight in columns:
            row.grid_columnconfigure(
                index,
                weight=weight,
            )

        # Order
        order_cell = ctk.CTkFrame(
            row,
            fg_color="transparent",
        )

        order_cell.grid(
            row=0,
            column=0,
            padx=8,
            pady=8,
            sticky="w",
        )

        ctk.CTkLabel(
            order_cell,
            text=format_order_id(order["id"]),
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=12,
                weight="bold",
            ),
            text_color=COLORS["text"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            order_cell,
            text=format_order_date(
                order["date_received"]
            ),
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=9,
            ),
            text_color=COLORS["muted"],
        ).pack(anchor="w")

        # Customer
        customer_cell = ctk.CTkFrame(
            row,
            fg_color="transparent",
        )

        customer_cell.grid(
            row=0,
            column=1,
            padx=8,
            pady=8,
            sticky="w",
        )

        ctk.CTkLabel(
            customer_cell,
            text=str(order["name"]),
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            text_color=COLORS["text"],
            anchor="w",
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            customer_cell,
            text=str(order["email"] or "No email"),
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=9,
            ),
            text_color=COLORS["muted"],
            anchor="w",
        ).pack(
            anchor="w",
        )

        # Weight
        ctk.CTkLabel(
            row,
            text=format_weight(order["weight_kg"]),
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
            ),
            text_color=COLORS["text"],
        ).grid(
            row=0,
            column=2,
            padx=8,
            sticky="w",
        )

        # Total
        ctk.CTkLabel(
            row,
            text=format_currency(order["total_price"]),
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            text_color=COLORS["text"],
        ).grid(
            row=0,
            column=3,
            padx=8,
            sticky="w",
        )

        # Status badge
        display_status = STATUS_COMPLETED if completed else STATUS_PENDING
        ctk.CTkLabel(
            row,
            text=display_status,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color="#FFFFFF",
            fg_color=STATUS_COLORS[display_status],
            corner_radius=12,
            width=130,
            height=27,
        ).grid(
            row=0,
            column=4,
            padx=8,
            sticky="w",
        )

        # Action buttons: no dropdown. Active orders can be completed or removed.
        action_cell = ctk.CTkFrame(
            row,
            fg_color="transparent",
        )

        action_cell.grid(
            row=0,
            column=5,
            padx=8,
            pady=7,
            sticky="w",
        )

        if not completed:
            ctk.CTkButton(
                action_cell,
                text="Completed",
                width=92,
                height=32,
                font=ctk.CTkFont(
                    family=FONT_FAMILY,
                    size=10,
                    weight="bold",
                ),
                fg_color=COLORS["success"],
                hover_color="#177A46",
                text_color="#FFFFFF",
                command=lambda oid=order_id: self.change_order_status(
                    oid,
                    "Completed",
                ),
            ).pack(
                side="left",
            )

            ctk.CTkButton(
                action_cell,
                text="Edit",
                width=60,
                height=32,
                font=ctk.CTkFont(
                    family=FONT_FAMILY,
                    size=10,
                    weight="bold",
                ),
                fg_color=COLORS["primary"],
                hover_color=COLORS["primary_hover"],
                text_color="#FFFFFF",
                command=lambda oid=order_id: self.open_edit_order(oid),
            ).pack(
                side="left",
                padx=(6, 0),
            )

            ctk.CTkButton(
                action_cell,
                text="Remove",
                width=72,
                height=32,
                font=ctk.CTkFont(
                    family=FONT_FAMILY,
                    size=10,
                    weight="bold",
                ),
                fg_color=COLORS["danger"],
                hover_color="#B93636",
                text_color="#FFFFFF",
                command=lambda oid=order_id: self.confirm_remove_order(oid),
            ).pack(
                side="left",
                padx=(6, 0),
            )
        else:
            ctk.CTkButton(
                action_cell,
                text="Remove",
                width=72,
                height=32,
                font=ctk.CTkFont(
                    family=FONT_FAMILY,
                    size=10,
                    weight="bold",
                ),
                fg_color=COLORS["danger"],
                hover_color="#B93636",
                text_color="#FFFFFF",
                command=lambda oid=order_id: self.confirm_remove_order(oid),
            ).pack(
                side="left",
            )

    def show_empty_state(self, title, message):
        holder = ctk.CTkFrame(
            self.orders_list,
            fg_color="transparent",
        )

        holder.pack(
            fill="x",
            pady=55,
        )

        ctk.CTkLabel(
            holder,
            text=title,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=18,
                weight="bold",
            ),
            text_color=COLORS["text"],
        ).pack()

        ctk.CTkLabel(
            holder,
            text=message,
            font=ctk.CTkFont(
                family=FONT_FAMILY,
                size=11,
            ),
            text_color=COLORS["muted"],
        ).pack(
            pady=(5, 0),
        )

    # ============================================================
    # REMOVE ORDER
    # ============================================================

    def open_edit_order(self, order_id):
        """Open the Edit Order dialog for the given order id."""
        from gui.edit_order import EditOrderWindow

        order = self.db.get_order(order_id)
        if order is None:
            messagebox.showwarning(
                "Order Not Found",
                f"Order {format_order_id(order_id)} no longer exists.",
                parent=self,
            )
            self.refresh_all()
            return

        EditOrderWindow(self, self.db, order, on_saved=self.refresh_all)

    def open_edit_order(self, order_id):
        """Open the Edit Order dialog for the given order id."""
        from gui.edit_order import EditOrderWindow

        order = self.db.get_order(order_id)
        if order is None:
            messagebox.showwarning(
                "Order Not Found",
                f"Order {format_order_id(order_id)} no longer exists.",
                parent=self,
            )
            self.refresh_all()
            return

        EditOrderWindow(self, self.db, order, on_saved=self.refresh_all)

    def confirm_remove_order(self, order_id):
        """Ask for confirmation before permanently removing an order."""
        order = self.db.get_order(order_id)
        if order is None:
            messagebox.showwarning(
                "Order Not Found",
                f"Order {format_order_id(order_id)} no longer exists.",
                parent=self,
            )
            self.refresh_all()
            return

        confirmed = messagebox.askyesno(
            "Remove Order",
            (
                f"Remove order {format_order_id(order_id)}?\n\n"
                f"Customer: {order['name']}\n"
                f"Weight: {format_weight(order['weight_kg'])}\n"
                f"Total: {format_currency(order['total_price'])}\n\n"
                "This removes the order from the database. "
                "The customer record will be kept."
            ),
            icon="warning",
            parent=self,
        )

        if not confirmed:
            return

        try:
            removed = self.db.delete_order(order_id)
        except MySQLError as exc:
            self.show_database_error(
                f"Order {format_order_id(order_id)} could not be removed.",
                exc,
            )
            return

        if removed:
            self.refresh_all()
            self.show_toast(
                f"Order {format_order_id(order_id)} removed.",
                "info",
            )
        else:
            self.refresh_all()
            messagebox.showwarning(
                "Order Not Found",
                f"Order {format_order_id(order_id)} no longer exists.",
                parent=self,
            )

    # ============================================================
    # STATUS WORKFLOW
    # ============================================================

    def change_order_status(
        self,
        order_id,
        new_status,
    ):
        try:
            updated = self.db.update_status(
                order_id,
                new_status,
            )
        except (MySQLError, ValueError) as exc:
            self.show_database_error(
                f"Order {format_order_id(order_id)} could not be updated.",
                exc,
            )
            self.after(
                100,
                self.load_orders,
            )
            return

        if not updated:
            messagebox.showwarning(
                "Order Not Found",
                f"Order {format_order_id(order_id)} no longer exists.",
                parent=self,
            )
            self.refresh_all()
            return

        self.update_statistics()
        self.load_orders()

        if new_status == "Completed":
            self.send_completion_email_async(
                order_id
            )
        else:
            self.show_toast(
                f"Order {format_order_id(order_id)} is still Pending.",
                "info",
            )

    def send_completion_email_async(self, order_id):
        order = self.db.get_order(
            order_id
        )

        if order is None:
            return

        customer_email = (
            order["email"] or ""
        ).strip()

        if not customer_email:
            self.show_toast(
                (
                    f"Order {format_order_id(order_id)} completed, "
                    "but the customer has no Gmail address."
                ),
                "error",
            )
            return

        if not self.gmail_service.is_configured():
            result = messagebox.askyesno(
                "Gmail Not Configured",
                (
                    f"Order {format_order_id(order_id)} is now Completed.\n\n"
                    "Gmail has not been configured, so the customer cannot "
                    "receive the automatic email yet.\n\n"
                    "Open Gmail Email Settings now?"
                ),
                parent=self,
            )

            if result:
                self.open_email_settings()

            return

        if order_id in self._email_sending_orders:
            return

        self._email_sending_orders.add(
            order_id
        )

        self.load_orders()

        worker = threading.Thread(
            target=self._send_completion_email_worker,
            args=(order,),
            daemon=True,
        )

        worker.start()

    def _send_completion_email_worker(self, order):
        try:
            self.gmail_service.send_order_completed_email(
                customer_name=order["name"],
                customer_email=order["email"],
                order_id=order["id"],
                weight=order["weight_kg"],
                total=order["total_price"],
                date_received=order["date_received"],
            )

            self.after(
                0,
                lambda oid=order["id"]: (
                    self.email_send_finished(
                        oid,
                        True,
                        None,
                    )
                ),
            )

        except Exception as exc:
            self.after(
                0,
                lambda oid=order["id"], error=exc: (
                    self.email_send_finished(
                        oid,
                        False,
                        error,
                    )
                ),
            )

    def email_send_finished(
        self,
        order_id,
        success,
        error,
    ):
        self._email_sending_orders.discard(
            order_id
        )

        self.load_orders()

        if success:
            self.show_toast(
                (
                    f"Order {format_order_id(order_id)} completed. "
                    "Email sent to the customer."
                ),
                "success",
                5000,
            )
        else:
            messagebox.showerror(
                "Customer Email Failed",
                (
                    f"Order {format_order_id(order_id)} was marked "
                    "Completed, but the email could not be sent.\n\n"
                    f"Customer email: "
                    f"{self.db.get_order(order_id)['email']}\n\n"
                    f"Error:\n{error}\n\n"
                    "Check the Gmail settings and internet connection before "
                    "processing future completion notifications."
                ),
                parent=self,
            )

    def resend_completed_email(self, order_id):
        self.send_completion_email_async(
            order_id
        )

    # ============================================================
    # RECEIPT / EMAIL SETTINGS
    # ============================================================

    def open_email_settings(self):
        EmailSettingsWindow(
            self,
            self.gmail_service,
            self.update_email_status,
        )

    def update_email_status(self):
        if self.gmail_service.is_configured():
            self.email_status_label.configure(
                text=(
                    "Email: Ready\n"
                    + self.gmail_service.sender_email
                ),
                text_color="#7CFC9A",
            )
        else:
            self.email_status_label.configure(
                text="Email: Not configured",
                text_color="#F5C542",
            )

    # ============================================================
    # STATISTICS / REFRESH
    # ============================================================

    def update_statistics(self):
        try:
            stats = self.db.get_statistics()
        except MySQLError as exc:
            self.show_database_error(
                "Could not load dashboard statistics.",
                exc,
            )
            return

        self.total_orders_value.configure(
            text=f"{stats['total_orders']:,}"
        )

        self.total_revenue_value.configure(
            text=format_currency(
                stats["total_revenue"]
            )
        )

        for status in STATUSES:
            self.status_count_labels[
                status
            ].configure(
                text=str(
                    stats["counts"][status]
                )
            )

    def refresh_all(self):
        self.update_statistics()
        self.load_orders()
        self.update_email_status()

    # ============================================================
    # APPEARANCE
    # ============================================================

    def toggle_appearance(self):
        current = ctk.get_appearance_mode()

        if current == "Light":
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")

    # ============================================================
    # TOAST
    # ============================================================

    def show_toast(
        self,
        message,
        kind="success",
        duration=3500,
    ):
        color = (
            COLORS["success"]
            if kind == "success"
            else COLORS["danger"]
            if kind == "error"
            else COLORS["primary"]
        )

        if not hasattr(
            self,
            "toast_frame",
        ):
            self.toast_frame = ctk.CTkFrame(
                self,
                corner_radius=10,
            )

            self.toast_label = ctk.CTkLabel(
                self.toast_frame,
                text="",
                font=ctk.CTkFont(
                    family=FONT_FAMILY,
                    size=11,
                    weight="bold",
                ),
                text_color="#FFFFFF",
                wraplength=430,
                justify="left",
            )

            self.toast_label.pack(
                padx=14,
                pady=9,
            )

        self.toast_frame.configure(
            fg_color=color
        )

        self.toast_label.configure(
            text=message
        )

        self.toast_frame.place(
            relx=1.0,
            rely=1.0,
            anchor="se",
            x=-22,
            y=-22,
        )

        self.toast_frame.lift()

        self.after(
            duration,
            self.hide_toast,
        )

    def hide_toast(self):
        if hasattr(
            self,
            "toast_frame",
        ):
            self.toast_frame.place_forget()

    def show_database_error(
        self,
        summary,
        error,
    ):
        messagebox.showerror(
            "Database Error",
            f"{summary}\n\n{error}",
            parent=self,
        )

    # ============================================================
    # SHUTDOWN
    # ============================================================

    def logout(self):
        if not messagebox.askyesno(
            "Logout",
            "Log out of the system?",
            parent=self,
        ):
            return

        self.db.close()
        self.destroy()

        from auth import AuthService
        from gui.login_window import LoginWindow

        db = LaundryDatabase()
        auth = AuthService(db)

        def on_login_success():
            gmail_service = GmailService(CONFIG_PATH)
            app = Application(db, gmail_service)
            app.mainloop()

        LoginWindow(auth, on_login_success).mainloop()

    def on_close(self):
        try:
            self.db.close()
        finally:
            self.destroy()


def main():
    ctk.set_appearance_mode("Light")
    ctk.set_default_color_theme("blue")

    # Import login components here so a login failure doesn't crash the app.
    try:
        from auth import AuthService
        from gui.login_window import LoginWindow
    except ImportError as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            APP_TITLE,
            f"Login components missing.\n\n{exc}",
        )
        root.destroy()
        return

    try:
        database = LaundryDatabase()
    except (MySQLError, OSError) as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            APP_TITLE,
            (
                "Could not connect to the MySQL database.\n\n"
                f"Host: {DB_HOST}\nDatabase: {DB_NAME}\n\n"
                f"{exc}"
            ),
        )
        root.destroy()
        return

    auth = AuthService(database)

    def on_login_success():
        gmail_service = GmailService(CONFIG_PATH)
        app = Application(database, gmail_service)
        app.mainloop()

    login = LoginWindow(auth, on_login_success)
    login.mainloop()


if __name__ == "__main__":
    main()