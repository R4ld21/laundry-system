"""Login authentication against the Users table."""

import hashlib


class AuthService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _hash(password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def authenticate(self, username, password):
        username = (username or "").strip()
        if not username or not password:
            return False

        row = self.db.query_one(
            "SELECT PasswordHash FROM Users WHERE Username = %s",
            (username,),
        )
        if not row:
            return False

        return row["PasswordHash"] == self._hash(password)