"""Edit an existing order — real Update from CRUD."""

import customtkinter as ctk
from tkinter import messagebox

from config import COLORS, FONT_FAMILY
from validators import (
    calculate_total,
    format_currency,
    parse_weight,
    validate_email,
    validate_name,
)


class EditOrderWindow(ctk.CTkToplevel):
    def __init__(self, master, db, order, on_saved):
        super().__init__(master)
        self.db = db
        self.order = order
        self.on_saved = on_saved

        self.title(f"Edit Order #{order['id']:03d}")
        self.geometry("520x520")
        self.resizable(False, True)
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text=f"Edit Order #{order['id']:03d}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, padx=25, pady=(22, 6), sticky="w")

        ctk.CTkLabel(
            self,
            text="Change the customer name, Gmail, or weight. Total is recalculated automatically.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLORS["muted"],
            wraplength=460,
            justify="left",
        ).grid(row=1, column=0, padx=25, pady=(0, 18), sticky="w")

        ctk.CTkLabel(
            self, text="Customer Name",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLORS["muted"],
        ).grid(row=2, column=0, padx=25, sticky="w")

        self.name_entry = ctk.CTkEntry(self, height=38)
        self.name_entry.insert(0, order["name"])
        self.name_entry.grid(row=3, column=0, padx=25, pady=(4, 14), sticky="ew")

        ctk.CTkLabel(
            self, text="Gmail Address",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLORS["muted"],
        ).grid(row=4, column=0, padx=25, sticky="w")

        self.email_entry = ctk.CTkEntry(self, height=38)
        self.email_entry.insert(0, order["email"] or "")
        self.email_entry.grid(row=5, column=0, padx=25, pady=(4, 14), sticky="ew")

        ctk.CTkLabel(
            self, text="Weight (kg)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLORS["muted"],
        ).grid(row=6, column=0, padx=25, sticky="w")

        self.weight_entry = ctk.CTkEntry(self, height=38)
        self.weight_entry.insert(0, str(order["weight_kg"]))
        self.weight_entry.grid(row=7, column=0, padx=25, pady=(4, 4), sticky="ew")
        self.weight_entry.bind("<KeyRelease>", self.update_preview)

        self.preview_label = ctk.CTkLabel(
            self,
            text=f"New total: {format_currency(order['total_price'])}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLORS["primary"],
        )
        self.preview_label.grid(row=8, column=0, padx=25, pady=(6, 18), sticky="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=9, column=0, padx=25, pady=(0, 22), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            btn_frame, text="Cancel", height=40,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["secondary_hover"],
            text_color=COLORS["text"],
            command=self.destroy,
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(
            btn_frame, text="Save Changes", height=40,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            command=self.save,
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    def update_preview(self, event=None):
        try:
            weight = parse_weight(self.weight_entry.get())
            total = calculate_total(weight)
            self.preview_label.configure(
                text=f"New total: {format_currency(total)}"
            )
        except ValueError:
            self.preview_label.configure(text="New total: —")

    def save(self):
        try:
            name = validate_name(self.name_entry.get())
            email = validate_email(self.email_entry.get())
            weight = parse_weight(self.weight_entry.get())
            total = calculate_total(weight)
        except ValueError as exc:
            messagebox.showerror("Check Details", str(exc), parent=self)
            return

        try:
            ok = self.db.update_order(
                self.order["id"], name, email, weight, total,
            )
        except Exception as exc:
            messagebox.showerror("Database Error", str(exc), parent=self)
            return

        if not ok:
            messagebox.showwarning(
                "Order Not Found",
                "That order no longer exists.",
                parent=self,
            )
            self.destroy()
            return

        self.on_saved()
        self.destroy()