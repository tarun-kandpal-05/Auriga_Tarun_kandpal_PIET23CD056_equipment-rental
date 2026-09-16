from datetime import date, datetime, timedelta
import sqlite3

from flask import Flask, flash, redirect, render_template, request, url_for

from database import get_db, init_db


app = Flask(__name__)
app.secret_key = "equipment-rental-development-key"
MAX_ACTIVE_ITEMS = 3
DEFAULT_RENTAL_DAYS = 7


def today():
	return date.today()


def parse_date(value, fallback=None):
	if not value:
		return fallback
	try:
		return datetime.strptime(value, "%Y-%m-%d").date()
	except ValueError:
		return None


def rental_status(row):
	if row["returned_at"]:
		return "Returned"
	due = datetime.fromisoformat(row["due_at"]).date()
	if today() > due:
		return "Overdue"
	if (due - today()).days <= 1:
		return "Due Soon"
	return "Active"


def days_overdue(row):
	return max(0, (today() - datetime.fromisoformat(row["due_at"]).date()).days)


def active_count(conn, borrower_id):
	return conn.execute(
		"SELECT COUNT(*) FROM rentals WHERE borrower_id = ? AND returned_at IS NULL", (borrower_id,)
	).fetchone()[0]


def get_or_create_borrower(conn, name, student_id, contact):
	name, student_id, contact = name.strip(), student_id.strip(), contact.strip()
	if not name or not student_id:
		raise ValueError("Borrower name and student ID are required.")
	borrower = conn.execute("SELECT * FROM borrowers WHERE student_id = ?", (student_id,)).fetchone()
	if borrower:
		if borrower["name"].lower() != name.lower():
			raise ValueError("That student ID belongs to another borrower.")
		conn.execute("UPDATE borrowers SET contact = ? WHERE id = ?", (contact, borrower["id"]))
		return borrower["id"]
	return conn.execute(
		"INSERT INTO borrowers (name, student_id, contact) VALUES (?, ?, ?)", (name, student_id, contact)
	).lastrowid


def overlapping_reserved(conn, type_id, start, end):
	return conn.execute(
		"""SELECT COALESCE(SUM(quantity), 0) FROM reservations
		WHERE equipment_type_id = ? AND status = 'confirmed'
		AND start_date < ? AND end_date > ?""",
		(type_id, end.isoformat(), start.isoformat()),
	).fetchone()[0]


@app.context_processor
def template_helpers():
	return {"today": today(), "rental_status": rental_status, "days_overdue": days_overdue, "max_active_items": MAX_ACTIVE_ITEMS}


@app.route("/")
def dashboard():
	conn = get_db()
	stats = {
		"total": conn.execute("SELECT COUNT(*) FROM equipment_units").fetchone()[0],
		"available": conn.execute("SELECT COUNT(*) FROM equipment_units WHERE status='available'").fetchone()[0],
		"borrowed": conn.execute("SELECT COUNT(*) FROM equipment_units WHERE status='borrowed'").fetchone()[0],
		"overdue": conn.execute("SELECT COUNT(*) FROM rentals WHERE returned_at IS NULL AND date(due_at) < date('now')").fetchone()[0],
		"reservations": conn.execute("SELECT COUNT(*) FROM reservations WHERE status='confirmed' AND end_date >= date('now')").fetchone()[0],
		"fees": conn.execute("SELECT COALESCE(SUM(late_fee), 0) FROM rentals WHERE returned_at IS NULL AND date(due_at) < date('now')").fetchone()[0],
	}
	recent = conn.execute("""SELECT r.*, b.name borrower_name, u.asset_code, t.name equipment_name
		FROM rentals r JOIN borrowers b ON b.id=r.borrower_id JOIN equipment_units u ON u.id=r.equipment_unit_id
		JOIN equipment_types t ON t.id=u.equipment_type_id ORDER BY r.id DESC LIMIT 8""").fetchall()
	upcoming = conn.execute("""SELECT r.*, b.name borrower_name, t.name equipment_name FROM reservations r
		JOIN borrowers b ON b.id=r.borrower_id JOIN equipment_types t ON t.id=r.equipment_type_id
		WHERE r.status='confirmed' AND r.end_date >= date('now') ORDER BY r.start_date LIMIT 5""").fetchall()
	conn.close()
	return render_template("dashboard.html", stats=stats, recent=recent, upcoming=upcoming)


@app.route("/equipment")
def equipment():
	conn = get_db()
	types = conn.execute("""SELECT t.*, COUNT(u.id) total,
		SUM(CASE WHEN u.status='available' THEN 1 ELSE 0 END) available,
		SUM(CASE WHEN u.status='borrowed' THEN 1 ELSE 0 END) borrowed
		FROM equipment_types t LEFT JOIN equipment_units u ON u.equipment_type_id=t.id GROUP BY t.id""").fetchall()
	units = conn.execute("SELECT u.*, t.name type_name FROM equipment_units u JOIN equipment_types t ON t.id=u.equipment_type_id ORDER BY t.name, u.asset_code").fetchall()
	conn.close()
	return render_template("equipment.html", types=types, units=units)


@app.route("/borrow", methods=["GET", "POST"])
def borrow():
	conn = get_db()
	types = conn.execute("SELECT * FROM equipment_types ORDER BY name").fetchall()
	if request.method == "POST":
		try:
			type_id = int(request.form.get("equipment_type_id", 0))
			quantity = int(request.form.get("quantity", 0))
			due = parse_date(request.form.get("due_date"), today() + timedelta(days=DEFAULT_RENTAL_DAYS))
			if quantity <= 0:
				raise ValueError("Quantity must be greater than zero.")
			if not due or due < today():
				raise ValueError("Due date must be today or a future date.")
			equipment_type = conn.execute("SELECT * FROM equipment_types WHERE id=?", (type_id,)).fetchone()
			if not equipment_type:
				raise ValueError("Select a valid equipment type.")
			units = conn.execute("SELECT * FROM equipment_units WHERE equipment_type_id=? AND status='available' LIMIT ?", (type_id, quantity)).fetchall()
			if len(units) < quantity:
				raise ValueError(f"Only {len(units)} unit(s) are available for this equipment type.")
			borrower_id = get_or_create_borrower(conn, request.form.get("name", ""), request.form.get("student_id", ""), request.form.get("contact", ""))
			if active_count(conn, borrower_id) + quantity > MAX_ACTIVE_ITEMS:
				raise ValueError(f"Borrowing limit exceeded. Maximum active equipment per borrower is {MAX_ACTIVE_ITEMS}.")
			borrowed_at = datetime.now().replace(microsecond=0).isoformat(sep=" ")
			for unit in units:
				conn.execute("INSERT INTO rentals (borrower_id,equipment_unit_id,borrowed_at,due_at,deposit,status) VALUES (?,?,?,?,?,'active')", (borrower_id, unit["id"], borrowed_at, due.isoformat(), equipment_type["deposit_amount"]))
				conn.execute("UPDATE equipment_units SET status='borrowed' WHERE id=?", (unit["id"],))
			conn.commit()
			flash(f"Borrowed {quantity} {equipment_type['name']}(s). Deposit recorded: ₹{equipment_type['deposit_amount'] * quantity:.0f}.", "success")
			return redirect(url_for("rentals"))
		except (ValueError, sqlite3.Error) as exc:
			conn.rollback()
			flash(str(exc), "danger")
	conn.close()
	return render_template("borrow.html", types=types, default_due=(today() + timedelta(days=DEFAULT_RENTAL_DAYS)).isoformat())


@app.route("/rentals")
def rentals():
	conn = get_db()
	rows = conn.execute("""SELECT r.*, b.name borrower_name, b.student_id, u.asset_code, t.name equipment_name, t.daily_late_fee
		FROM rentals r JOIN borrowers b ON b.id=r.borrower_id JOIN equipment_units u ON u.id=r.equipment_unit_id
		JOIN equipment_types t ON t.id=u.equipment_type_id ORDER BY r.id DESC""").fetchall()
	conn.close()
	return render_template("rentals.html", rentals=rows)


@app.route("/rentals/<int:rental_id>/transfer", methods=["GET", "POST"])
def transfer_rental(rental_id):
	conn = get_db()
	rental = conn.execute("""SELECT r.*, b.name borrower_name, b.student_id, u.asset_code,
		t.name equipment_name FROM rentals r JOIN borrowers b ON b.id=r.borrower_id
		JOIN equipment_units u ON u.id=r.equipment_unit_id JOIN equipment_types t ON t.id=u.equipment_type_id
		WHERE r.id=?""", (rental_id,)).fetchone()
	if not rental:
		conn.close()
		flash("Rental record not found.", "danger")
		return redirect(url_for("rentals"))
	if request.method == "POST":
		try:
			if rental["returned_at"] or rental["status"] != "active":
				raise ValueError("Only active loans can be transferred.")
			new_borrower_id = get_or_create_borrower(
				conn,
				request.form.get("name", ""),
				request.form.get("student_id", ""),
				request.form.get("contact", ""),
			)
			if new_borrower_id == rental["borrower_id"]:
				raise ValueError("A loan cannot be transferred to the same borrower.")
			if active_count(conn, new_borrower_id) >= MAX_ACTIVE_ITEMS:
				raise ValueError(f"Transfer rejected. The new borrower already has the maximum {MAX_ACTIVE_ITEMS} active units.")
			conn.execute("UPDATE rentals SET borrower_id=? WHERE id=? AND returned_at IS NULL", (new_borrower_id, rental_id))
			conn.execute("UPDATE notifications SET borrower_id=? WHERE rental_id=?", (new_borrower_id, rental_id))
			conn.commit()
			flash(
				f"{rental['asset_code']} transferred from {rental['borrower_name']} to {request.form['name'].strip()}. "
				f"Original due date remains {rental['due_at'][:10]}.",
				"success",
			)
			conn.close()
			return redirect(url_for("rentals"))
		except (ValueError, sqlite3.Error) as exc:
			conn.rollback()
			flash(str(exc), "danger")
	conn.close()
	return render_template("transfer.html", rental=rental)


@app.post("/returns/<int:rental_id>")
def return_rental(rental_id):
	conn = get_db()
	rental = conn.execute("""SELECT r.*, u.asset_code, t.daily_late_fee FROM rentals r
		JOIN equipment_units u ON u.id=r.equipment_unit_id JOIN equipment_types t ON t.id=u.equipment_type_id WHERE r.id=?""", (rental_id,)).fetchone()
	if not rental:
		flash("Rental record not found.", "danger")
	elif rental["returned_at"]:
		flash("This rental has already been returned.", "warning")
	else:
		returned = parse_date(request.form.get("return_date"), today())
		due = datetime.fromisoformat(rental["due_at"]).date()
		if not returned or returned > today():
			flash("Return date must be today or earlier.", "danger")
		else:
			overdue_days = max(0, (returned - due).days)
			fee = overdue_days * rental["daily_late_fee"]
			refund = max(0, rental["deposit"] - fee)
			conn.execute("UPDATE rentals SET returned_at=?, late_fee=?, refund_amount=?, status='returned' WHERE id=?", (returned.isoformat(), fee, refund, rental_id))
			conn.execute("UPDATE equipment_units SET status='available' WHERE id=?", (rental["equipment_unit_id"],))
			conn.commit()
			flash(f"{rental['asset_code']} returned. Late fee: ₹{fee:.0f}; deposit refund: ₹{refund:.0f}.", "success")
	conn.close()
	return redirect(url_for("rentals"))


@app.route("/reservations", methods=["GET", "POST"])
def reservations():
	conn = get_db()
	types = conn.execute("SELECT * FROM equipment_types ORDER BY name").fetchall()
	if request.method == "POST":
		try:
			type_id = int(request.form.get("equipment_type_id", 0))
			quantity = int(request.form.get("quantity", 0))
			start, end = parse_date(request.form.get("start_date")), parse_date(request.form.get("end_date"))
			if quantity <= 0 or not start or not end or end < start or start < today():
				raise ValueError("Enter a positive quantity and a valid future date range.")
			borrower_id = get_or_create_borrower(conn, request.form.get("name", ""), request.form.get("student_id", ""), request.form.get("contact", ""))
			total = conn.execute("SELECT COUNT(*) FROM equipment_units WHERE equipment_type_id=?", (type_id,)).fetchone()[0]
			if not total:
				raise ValueError("Select a valid equipment type.")
			reserved = overlapping_reserved(conn, type_id, start, end)
			if reserved + quantity > total:
				raise ValueError(f"Reservation rejected: only {max(0, total - reserved)} unit(s) remain for that period.")
			conn.execute("INSERT INTO reservations (borrower_id,equipment_type_id,quantity,start_date,end_date) VALUES (?,?,?,?,?)", (borrower_id, type_id, quantity, start.isoformat(), end.isoformat()))
			conn.commit()
			flash("Reservation confirmed.", "success")
			return redirect(url_for("reservations"))
		except (ValueError, sqlite3.Error) as exc:
			conn.rollback()
			flash(str(exc), "danger")
	rows = conn.execute("""SELECT r.*, b.name borrower_name, t.name equipment_name FROM reservations r
		JOIN borrowers b ON b.id=r.borrower_id JOIN equipment_types t ON t.id=r.equipment_type_id ORDER BY r.start_date""").fetchall()
	conn.close()
	return render_template("reservations.html", reservations=rows, types=types)


@app.post("/reservations/<int:reservation_id>/cancel")
def cancel_reservation(reservation_id):
	conn = get_db()
	conn.execute("UPDATE reservations SET status='cancelled' WHERE id=? AND status='confirmed'", (reservation_id,))
	conn.commit()
	conn.close()
	flash("Reservation cancelled.", "success")
	return redirect(url_for("reservations"))


@app.route("/availability")
def availability():
	conn = get_db()
	types = conn.execute("SELECT * FROM equipment_types ORDER BY name").fetchall()
	result = None
	type_id = request.args.get("equipment_type_id", type=int)
	start, end = parse_date(request.args.get("start_date")), parse_date(request.args.get("end_date"))
	if type_id and start and end and end >= start:
		total = conn.execute("SELECT COUNT(*) FROM equipment_units WHERE equipment_type_id=?", (type_id,)).fetchone()[0]
		reserved = overlapping_reserved(conn, type_id, start, end)
		unavailable = conn.execute("SELECT COUNT(*) FROM equipment_units WHERE equipment_type_id=? AND status!='available'", (type_id,)).fetchone()[0]
		result = {"total": total, "reserved": reserved, "unavailable": unavailable, "available": max(0, total - reserved - unavailable)}
	conn.close()
	return render_template("availability.html", types=types, result=result, selected=type_id, start=request.args.get("start_date", ""), end=request.args.get("end_date", ""))


@app.route("/notifications")
def notifications():
	conn = get_db()
	overdue = conn.execute("""SELECT r.*, b.name borrower_name, u.asset_code, t.daily_late_fee FROM rentals r
		JOIN borrowers b ON b.id=r.borrower_id JOIN equipment_units u ON u.id=r.equipment_unit_id JOIN equipment_types t ON t.id=u.equipment_type_id
		WHERE r.returned_at IS NULL AND date(r.due_at)<date('now') ORDER BY r.due_at""").fetchall()
	due_soon = conn.execute("""SELECT r.*, b.name borrower_name, u.asset_code FROM rentals r JOIN borrowers b ON b.id=r.borrower_id JOIN equipment_units u ON u.id=r.equipment_unit_id
		WHERE r.returned_at IS NULL AND date(r.due_at) BETWEEN date('now') AND date('now','+1 day')""").fetchall()
	upcoming = conn.execute("""SELECT r.*, b.name borrower_name, t.name equipment_name FROM reservations r JOIN borrowers b ON b.id=r.borrower_id JOIN equipment_types t ON t.id=r.equipment_type_id
		WHERE r.status='confirmed' AND date(r.start_date) BETWEEN date('now') AND date('now','+7 day') ORDER BY r.start_date""").fetchall()
	conn.close()
	return render_template("notifications.html", overdue=overdue, due_soon=due_soon, upcoming=upcoming)


@app.post("/notifications/remind/<int:rental_id>")
def send_reminder(rental_id):
	conn = get_db()
	rental = conn.execute("SELECT r.*, b.id borrower_id, u.asset_code FROM rentals r JOIN borrowers b ON b.id=r.borrower_id JOIN equipment_units u ON u.id=r.equipment_unit_id WHERE r.id=?", (rental_id,)).fetchone()
	if rental:
		due = datetime.fromisoformat(rental["due_at"]).date()
		days = max(0, (today() - due).days)
		message = f"{rental['asset_code']} is overdue by {days} day(s). Please return it to the AV room."
		conn.execute("INSERT INTO notifications (borrower_id,rental_id,message,created_at) VALUES (?,?,?,?)", (rental["borrower_id"], rental_id, message, datetime.now().isoformat(sep=" ", timespec="seconds")))
		conn.commit()
		flash("In-app reminder created.", "success")
	else:
		flash("Rental record not found.", "danger")
	conn.close()
	return redirect(url_for("notifications"))


@app.route("/notifications/inbox")
def notification_inbox():
	conn = get_db()
	rows = conn.execute("SELECT n.*, b.name borrower_name FROM notifications n JOIN borrowers b ON b.id=n.borrower_id ORDER BY n.created_at DESC").fetchall()
	conn.close()
	return render_template("notification_inbox.html", notifications=rows)


if __name__ == "__main__":
	init_db()
	app.run(debug=True, host="0.0.0.0", port=5000)
