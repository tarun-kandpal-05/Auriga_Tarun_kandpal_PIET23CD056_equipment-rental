# AV Room Equipment Rental Management System

A web-based equipment rental management system for a college AV room.

## Problem

The AV room currently relies on a paper register, which makes it difficult to know:

- which equipment is available
- who currently has an item
- when equipment is due
- whether equipment can be reserved for a specific date range
- which borrowers have overdue equipment
- how much late fee should be deducted from a refundable deposit

## Features

- Physical-unit inventory with asset codes and availability status
- Borrowing and returns with server-side validation
- Configurable deposits and late-fee calculation
- Three active-unit borrowing limit per borrower
- Date-based availability lookup
- Reservations with overlap/capacity protection
- Active loan transfer between borrowers without changing the physical loan
- Overdue and due-soon views with in-app reminder notifications
- Idempotent demo seed data for a useful first launch

## Technology Stack

- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript
- Bootstrap

## Requirements

- Python 3.10 or newer
- Flask (installed from `requirements.txt`)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Open `http://127.0.0.1:5000`. In GitHub Codespaces, open the forwarded port 5000 from the Ports panel.

## Database

SQLite is stored in `equipment.db` and is created automatically on first startup. The first initialization creates 22 physical units, four equipment types, three sample borrowers, one active demo rental, and one future reservation. Seed insertion is skipped when equipment types already exist, so restarts do not duplicate data.

## Business Rules

- Default rental duration is 7 days; a future custom due date may be selected.
- A borrower may have at most 3 active physical units.
- Late fee is overdue days multiplied by the equipment type's daily fee.
- Refund is `max(0, deposit - late fee)`.
- Reservations overlap when `new_start < existing_end` and `new_end > existing_start`.
- A reservation is rejected if overlapping confirmed quantities exceed the physical capacity of that equipment type.
- Availability is calculated from physical unit status plus overlapping confirmed reservations.
- An active loan transfer changes only the rental's borrower. The original unit, borrowed date, due date, deposit, and rental ID are preserved; the unit becomes available only when it is returned.

## Debugging

Run `python app.py` from the repository root and inspect the terminal for Flask or SQLite errors. For a clean demo database, stop the app, remove `equipment.db`, and start it again; the seed data will be recreated.

## Main Routes

`/` dashboard, `/equipment` inventory, `/borrow` checkout, `/rentals` rental register and returns, `/reservations` reservations, `/availability` date-based capacity, `/notifications` reminders, and `/notifications/inbox` sent in-app reminders. Active rentals also expose a Transfer action.

