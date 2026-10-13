---
marp: true
theme: default
paginate: true
size: 16:9
style: |
  :root {
    --sky: #4FA8D8;
    --sky-dark: #2C7BA8;
    --bubble: #E8F4FB;
    --soft-blue: #D6ECF7;
    --deep: #14384D;
    --accent: #F2A65A;
    --muted: #5A7A8C;
  }

  section {
    background-color: #F5FAFD;
    background-image:
      radial-gradient(circle at 15% 25%, rgba(79, 168, 216, 0.08) 0%, transparent 18%),
      radial-gradient(circle at 82% 18%, rgba(79, 168, 216, 0.10) 0%, transparent 14%),
      radial-gradient(circle at 90% 78%, rgba(79, 168, 216, 0.07) 0%, transparent 16%),
      radial-gradient(circle at 8% 82%, rgba(242, 166, 90, 0.08) 0%, transparent 14%),
      repeating-linear-gradient(
        45deg,
        rgba(79, 168, 216, 0.025) 0px,
        rgba(79, 168, 216, 0.025) 1px,
        transparent 1px,
        transparent 14px
      ),
      repeating-linear-gradient(
        -45deg,
        rgba(79, 168, 216, 0.025) 0px,
        rgba(79, 168, 216, 0.025) 1px,
        transparent 1px,
        transparent 14px
      ),
      linear-gradient(160deg, #FFFFFF 0%, #EAF4FB 100%);
    color: var(--deep);
    font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
    font-size: 25px;
    padding: 55px 75px;
    line-height: 1.55;
    letter-spacing: 0.2px;
    position: relative;
  }

  section::before {
    content: "";
    position: absolute;
    top: 30px;
    right: 55px;
    width: 120px;
    height: 120px;
    border-radius: 50%;
    background:
      radial-gradient(circle at 30% 30%, #FFFFFF 0%, #E8F4FB 45%, #C9E2F0 100%);
    box-shadow:
      inset -12px -12px 24px rgba(79, 168, 216, 0.15),
      inset 6px 6px 12px rgba(255, 255, 255, 0.9),
      0 4px 20px rgba(79, 168, 216, 0.12);
    opacity: 0.55;
    pointer-events: none;
  }

  section::after {
    content: "";
    position: absolute;
    bottom: 45px;
    left: 40px;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background:
      radial-gradient(circle at 30% 30%, #FFFFFF 0%, #E8F4FB 60%, #C9E2F0 100%);
    box-shadow:
      inset -6px -6px 12px rgba(79, 168, 216, 0.15),
      inset 3px 3px 6px rgba(255, 255, 255, 0.9);
    opacity: 0.45;
    pointer-events: none;
  }

  h1 {
    color: var(--sky-dark);
    font-size: 60px;
    font-weight: 800;
    letter-spacing: -1px;
    margin: 0 0 18px 0;
    line-height: 1.1;
  }

  h2 {
    color: var(--sky-dark);
    font-size: 40px;
    font-weight: 700;
    padding-bottom: 12px;
    margin-bottom: 28px;
    letter-spacing: -0.5px;
    position: relative;
  }

  h2::after {
    content: "";
    position: absolute;
    left: 0;
    bottom: 0;
    width: 90px;
    height: 4px;
    background: linear-gradient(to right, var(--sky), var(--accent));
    border-radius: 4px;
  }

  h3 {
    color: var(--sky-dark);
    font-size: 26px;
    font-weight: 700;
    margin-top: 22px;
    margin-bottom: 10px;
  }

  strong {
    color: var(--sky-dark);
    font-weight: 700;
  }

  ul {
    list-style: none;
    padding-left: 0;
  }

  ul li {
    position: relative;
    padding-left: 30px;
    margin-bottom: 13px;
  }

  ul li::before {
    content: "";
    position: absolute;
    left: 4px;
    top: 12px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: radial-gradient(circle at 30% 30%, #FFFFFF, var(--sky) 80%);
    box-shadow: 0 1px 3px rgba(79, 168, 216, 0.35);
  }

  code {
    background: var(--soft-blue);
    color: var(--sky-dark);
    padding: 2px 10px;
    border-radius: 8px;
    font-family: 'Consolas', monospace;
    font-size: 0.9em;
    font-weight: 600;
  }

  hr {
    border: none;
    height: 2px;
    background: linear-gradient(to right, var(--sky), transparent);
    margin: 30px 0;
  }

  section.lead {
    background-color: #2C7BA8;
    background-image:
      radial-gradient(circle at 20% 30%, rgba(255, 255, 255, 0.15) 0%, transparent 25%),
      radial-gradient(circle at 78% 68%, rgba(255, 255, 255, 0.10) 0%, transparent 22%),
      radial-gradient(circle at 88% 18%, rgba(255, 255, 255, 0.08) 0%, transparent 18%),
      repeating-linear-gradient(
        45deg,
        rgba(255, 255, 255, 0.04) 0px,
        rgba(255, 255, 255, 0.04) 1px,
        transparent 1px,
        transparent 16px
      ),
      repeating-linear-gradient(
        -45deg,
        rgba(255, 255, 255, 0.04) 0px,
        rgba(255, 255, 255, 0.04) 1px,
        transparent 1px,
        transparent 16px
      ),
      linear-gradient(135deg, #4FA8D8 0%, #2C7BA8 100%);
    color: #FFFFFF;
    text-align: center;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 60px 80px;
  }

  section.lead::before {
    top: 40px;
    right: 70px;
    width: 140px;
    height: 140px;
    background:
      radial-gradient(circle at 30% 30%, rgba(255,255,255,0.9), rgba(255,255,255,0.4) 60%, rgba(255,255,255,0.1) 100%);
    box-shadow:
      inset -14px -14px 28px rgba(255,255,255,0.15),
      inset 8px 8px 16px rgba(255,255,255,0.4);
    opacity: 0.5;
  }

  section.lead::after {
    bottom: 50px;
    left: 60px;
    width: 80px;
    height: 80px;
    background:
      radial-gradient(circle at 30% 30%, rgba(255,255,255,0.85), rgba(255,255,255,0.3) 70%);
    box-shadow:
      inset -8px -8px 16px rgba(255,255,255,0.15),
      inset 4px 4px 8px rgba(255,255,255,0.4);
    opacity: 0.4;
  }

  section.lead h1 {
    color: #FFFFFF;
    font-size: 72px;
    text-shadow: 0 4px 20px rgba(0, 0, 0, 0.18);
    margin-bottom: 22px;
  }

  section.lead h3 {
    color: rgba(255, 255, 255, 0.92);
    font-weight: 400;
    font-size: 24px;
    letter-spacing: 0.5px;
  }

  section.lead strong {
    color: #FFFFFF;
  }

  section.lead p {
    color: rgba(255, 255, 255, 0.9);
    font-size: 20px;
  }
---

<!-- _class: lead -->

# Laundry Management System
### Event-Driven Object-Oriented Programming Final Project

**Presented by:** [Your Group Name]
**Date:** October 2026

---

## Problem & Users

### The Problem
- Lost order tickets
- Errors in weight and price calculation
- No automatic customer notifications

### Intended Users
- **Shop Staff** — Add orders, update status, send notifications
- **Shop Owner** — Monitor daily revenue and completed orders

### Objectives
1. Digitize the order intake and tracking process
2. Automate price calculation and receipt generation
3. Notify customers automatically when laundry is ready

---

## System Architecture

### Main Classes
- **`Application`** — Main GUI window and event controller
- **`LaundryDatabase`** — Handles all MySQL operations (CRUD)
- **`GmailService`** — Manages SMTP connection and email sending
- **`AuthService`** — Validates user login credentials

### OOP Principles
- **Encapsulation** — Database logic hidden inside `LaundryDatabase`
- **Separation of Concerns** — GUI, data, and business logic in separate files
- **Event-Driven** — Actions triggered by user clicks

---

## Database Design

### `Customers` Table
Stores reusable customer info (Name, Email)

### `Orders` Table
Links to a Customer — Weight, Rate, Total Price, Status

### `Users` Table
Stores hashed passwords for login (SHA-256)

### Relationship
**One Customer → Many Orders**  (1 : N)

---

## Core Features — CRUD

- **Create** — Add a new laundry order, calculate total
- **Read** — Display Pending and Completed orders
- **Update** — Edit customer details or order weight
- **Delete** — Remove an order with confirmation
- **Search** — Filter by name, Gmail, or order number

---

## Additional Features

- **Login Screen** — Secure access with hashed passwords
- **Automatic Email** — Completion notice sent to customer's Gmail
- **Receipt Generation** — Creates a `.txt` receipt for every order
- **Dashboard Statistics** — Total orders, revenue, status counts
- **Logout** — Safe exit back to the login screen

---

<!-- _class: lead -->

# Thank You