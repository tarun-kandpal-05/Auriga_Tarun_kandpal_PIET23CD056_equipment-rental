# Engineering Reasoning

## 1. Problem understanding

The AV room needs reliable tracking of each physical item, who has it, when it is due, and whether future requests can be fulfilled. The highest-risk errors are inconsistent inventory, double booking, and incorrect return charges.

## 2. Functional requirements

The implementation provides inventory, physical-unit borrowing, returns, deposits, late fees, borrower limits, date-range availability, reservations, conflict prevention, active-loan transfers, overdue views, and in-app reminders.

## 3. Non-functional requirements

The app is a small Flask/SQLite application with parameterized SQL, no external services, automatic initialization, readable templates, and a simple `python app.py` launch command.

## 4. Assumptions

The default rental period is 7 days and the maximum active equipment count is 3. DSLR and projector late fees are ₹50/day; microphone and tripod late fees are ₹20/day. Deposits are ₹1000, ₹1500, ₹500, and ₹300 respectively. These values live in `equipment_types` and can be changed without code changes.

## 5. Technology choice

Flask, SQLite, server-rendered HTML, Bootstrap 5, and small vanilla JavaScript keep setup and debugging appropriate for a college lending desk.

## 6. Architecture

`database.py` owns the SQLite connection, schema, and idempotent seed data. `app.py` owns route handlers, validation, business rules, and query composition. Templates provide the user interface and the static files provide light styling and confirmation behavior.

## 7. Database design

Equipment types describe a category and its fee policy. Equipment units represent each physical asset. Rentals connect a borrower to one physical unit, while reservations connect a borrower to a category and date range. Notifications optionally reference a rental.

## 8. Availability design

Current availability counts units whose status is `available`. Date-range availability additionally subtracts overlapping confirmed reservation quantities and currently unavailable units. No manually maintained quantity field is used.

## 9. Borrowing logic

The server validates quantity, date, equipment type, and physical stock, then finds or creates the borrower, checks the active-unit limit, inserts one rental per unit, records one deposit per unit, and marks those units borrowed in one transaction.

## 10. Reservation conflict logic

Confirmed reservations are considered overlapping using `new_start < existing_end AND new_end > existing_start`. Their quantities are summed and compared with the category's total physical units before insertion.

## 11. Return and late-fee logic

Returns are accepted once, calculate overdue days from the due date, persist the fee and refund, mark the rental returned, and make its physical unit available again. Overdue display state is derived from the current date and `returned_at`, rather than relying on a stale status value.

## 12. Deposit logic

The equipment type's deposit is recorded on every unit rental. Refund is never negative, so a fee larger than the deposit produces a zero refund.

## 13. Borrowing limit

The active count is the number of rentals for the borrower with no `returned_at`. A request is rejected if that count plus the requested quantity exceeds 3.

## 13a. Loan transfer

A transfer changes the existing active rental's `borrower_id` rather than creating a second rental. This preserves the same physical unit, rental ID, borrowed date, due date, deposit, and eventual return record. Since `equipment_units.status` is not modified, availability is identical before and after transfer. The new borrower must be different from the current borrower and must have fewer than 3 active rentals; the original borrower's active count decreases naturally. Existing notifications linked to the rental are reassigned to the new borrower so overdue or due-soon messages follow the current owner without creating duplicate reminders.

## 14. Notification design

The reminders page derives overdue, due-soon, and upcoming-reservation lists from current database dates. Send Reminder creates an in-app notification row; the inbox displays those rows. When a loan transfers, existing linked notifications use the new borrower. No email provider is required.

## 15. Validation strategy

All important rules are checked in Flask handlers as well as by SQLite constraints where useful. Invalid forms receive Bootstrap flash alerts instead of stack traces. SQL values are passed as parameters.

## 16. Testing strategy

The application was syntax-checked, initialized from SQLite, smoke-tested across every main route, and exercised through Flask's test client for successful borrowing, stock rejection, limit rejection, overdue fee/refund, overlapping reservation rejection, and reminder creation.

## 17. Trade-offs

There is no authentication, background scheduler, email integration, or admin CRUD UI. Those are intentionally outside the MVP so the core lending rules remain easy to inspect and run.

## 18. Possible future improvements

Add staff authentication and audit logs, equipment maintenance actions, a scheduled reminder job, richer borrower history, CSRF protection, and automated pytest coverage against a temporary database.
