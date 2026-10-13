"""All MySQL operations. Replaces the old pyodbc-based LaundryDatabase."""

from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal

import mysql.connector
from mysql.connector import Error as MySQLError

from config import (
    DATE_FORMAT,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    RATE_PER_KG,
    STATUSES,
)


class LaundryDatabase:
    """Encapsulates all SQL access for the laundry system."""

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

    # ---------- helpers ----------

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
        """Commit if the block succeeds; roll back on error."""
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

    # ---------- customers / orders ----------

    def save_customer(self, cursor, name, email):
        cursor.execute(
            "SELECT CustomerId FROM Customers WHERE LOWER(IFNULL(Email,'')) = LOWER(%s) LIMIT 1",
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
                (customer_id, Decimal(weight), RATE_PER_KG, Decimal(total), status, received),
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
                "(c.Name LIKE %s OR c.Email LIKE %s OR CAST(o.OrderId AS CHAR) LIKE %s)"
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
            "SELECT COUNT(*) AS total_orders, COALESCE(SUM(TotalPrice),0) AS total_revenue FROM Orders"
        )
        counts = {s: 0 for s in STATUSES}
        for row in self.query_all("SELECT Status AS status, COUNT(*) AS cnt FROM Orders GROUP BY Status"):
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
                    CompletedAt = CASE WHEN %s = 'Completed' THEN NOW() ELSE NULL END
                WHERE OrderId = %s
                """,
                (new_status, new_status, order_id),
            )
            return cursor.rowcount > 0

    def update_order(self, order_id, name, email, weight, total):
        """Update customer + order details (real Update from CRUD)."""
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
                "UPDATE Customers SET Name = %s, Email = %s WHERE CustomerId = %s",
                (name, email, customer_id),
            )
            cursor.execute(
                "UPDATE Orders SET WeightKg = %s, TotalPrice = %s WHERE OrderId = %s",
                (Decimal(weight), Decimal(total), order_id),
            )
        return True

    def get_order(self, order_id):
        return self.query_one(self.ORDER_SELECT + " WHERE o.OrderId = %s", (order_id,))

    def delete_order(self, order_id):
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM Orders WHERE OrderId = %s", (order_id,))
            return cursor.rowcount > 0

    def close(self):
        try:
            self.conn.close()
        except MySQLError:
            pass