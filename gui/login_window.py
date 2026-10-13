"""Login screen shown before the main application."""

import customtkinter as ctk
from tkinter import messagebox

from config import COLORS, FONT_FAMILY


class LoginWindow(ctk.CTk):
    def __init__(self, auth_service, on_success):
        super().__init__()
        self.auth_service = auth_service
        self.on_success = on_success

        self.title("Login - Laundry Management System")
        self.geometry("420x480")
        self.resizable(False, True)
        self.configure(fg_color=COLORS["main_bg"])

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="Laundry Management System",
            font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, padx=30, pady=(40, 5), sticky="ew")

        ctk.CTkLabel(
            self,
            text="Sign in to continue",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLORS["muted"],
        ).grid(row=1, column=0, padx=30, pady=(0, 25), sticky="ew")

        ctk.CTkLabel(
            self,
            text="Username",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLORS["muted"],
        ).grid(row=2, column=0, padx=30, sticky="w")

        self.username_entry = ctk.CTkEntry(
            self, height=40, placeholder_text="admin",
        )
        self.username_entry.grid(row=3, column=0, padx=30, pady=(4, 14), sticky="ew")

        ctk.CTkLabel(
            self,
            text="Password",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLORS["muted"],
        ).grid(row=4, column=0, padx=30, sticky="w")

        self.password_entry = ctk.CTkEntry(
            self, height=40, placeholder_text="\u2022" * 8, show="\u2022",
        )
        self.password_entry.grid(row=5, column=0, padx=30, pady=(4, 6), sticky="ew")

        self.error_label = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLORS["danger"],
        )
        self.error_label.grid(row=6, column=0, padx=30, pady=(0, 14), sticky="w")

        ctk.CTkButton(
            self,
            text="Login",
            height=42,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            command=self.attempt_login,
        ).grid(row=7, column=0, padx=30, pady=(0, 10), sticky="ew")

        ctk.CTkButton(
            self,
            text="Exit",
            height=36,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["secondary_hover"],
            text_color=COLORS["text"],
            command=self.destroy,
        ).grid(row=8, column=0, padx=30, pady=(0, 30), sticky="ew")

        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus_set())
        self.password_entry.bind("<Return>", lambda e: self.attempt_login())
        self.username_entry.focus_set()

    def attempt_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()

        if not username or not password:
            self.error_label.configure(text="Please enter username and password.")
            return

        if self.auth_service.authenticate(username, password):
            self.destroy()
            self.on_success()
        else:
            self.error_label.configure(text="Invalid username or password.")
            self.password_entry.delete(0, "end")
            self.password_entry.focus_set()