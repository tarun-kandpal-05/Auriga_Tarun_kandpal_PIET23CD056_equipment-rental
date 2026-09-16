import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

DATABASE = Path(__file__).parent / "equipment.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS equipment_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            daily_late_fee REAL NOT NULL DEFAULT 0,
            deposit_amount REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS equipment_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_type_id INTEGER NOT NULL,
            asset_code TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'available'
                CHECK (status IN ('available', 'borrowed', 'maintenance')),
            FOREIGN KEY (equipment_type_id)
                REFERENCES equipment_types(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS borrowers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            student_id TEXT NOT NULL UNIQUE,
            contact TEXT
        );

        CREATE TABLE IF NOT EXISTS rentals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id INTEGER NOT NULL,
            equipment_unit_id INTEGER NOT NULL,
            borrowed_at TEXT NOT NULL,
            due_at TEXT NOT NULL,
            returned_at TEXT,
            deposit REAL NOT NULL DEFAULT 0,
            late_fee REAL NOT NULL DEFAULT 0,
            refund_amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'returned')),
            FOREIGN KEY (borrower_id)
                REFERENCES borrowers(id),
            FOREIGN KEY (equipment_unit_id)
                REFERENCES equipment_units(id)
        );

        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id INTEGER NOT NULL,
            equipment_type_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed'
                CHECK (status IN ('confirmed', 'cancelled', 'completed')),
            FOREIGN KEY (borrower_id)
                REFERENCES borrowers(id),
            FOREIGN KEY (equipment_type_id)
                REFERENCES equipment_types(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id INTEGER NOT NULL,
            rental_id INTEGER,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (borrower_id)
                REFERENCES borrowers(id),
            FOREIGN KEY (rental_id)
                REFERENCES rentals(id)
        );
        """
    )

    seed_database(conn)

    conn.commit()
    conn.close()


def seed_database(conn):
    """Insert deterministic demo data only when a new database is empty."""
    if conn.execute("SELECT 1 FROM equipment_types LIMIT 1").fetchone():
        return

    types = [
        ("DSLR Camera", "Interchangeable-lens camera for events and productions", 50, 1000),
        ("Projector", "HD projector for classrooms and screenings", 50, 1500),
        ("Microphone", "Wired microphone for presentations and performances", 20, 500),
        ("Tripod", "Camera tripod with adjustable height", 20, 300),
    ]
    conn.executemany(
        "INSERT INTO equipment_types (name, description, daily_late_fee, deposit_amount) VALUES (?, ?, ?, ?)",
        types,
    )
    type_ids = {row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM equipment_types")}
    unit_counts = {"DSLR Camera": 5, "Projector": 3, "Microphone": 8, "Tripod": 6}
    prefixes = {"DSLR Camera": "DSLR", "Projector": "PROJ", "Microphone": "MIC", "Tripod": "TRIP"}
    for name, count in unit_counts.items():
        conn.executemany(
            "INSERT INTO equipment_units (equipment_type_id, asset_code, status) VALUES (?, ?, 'available')",
            [(type_ids[name], f"{prefixes[name]}-{number:03d}") for number in range(1, count + 1)],
        )
    conn.executemany(
        "INSERT INTO borrowers (name, student_id, contact) VALUES (?, ?, ?)",
        [
            ("Aarav Sharma", "DEMO001", "aarav@example.edu"),
            ("Media Club", "CLUB001", "media@example.edu"),
            ("Tech Society", "CLUB002", "tech@example.edu"),
        ],
    )
    borrower_ids = {row["student_id"]: row["id"] for row in conn.execute("SELECT id, student_id FROM borrowers")}
    projector_type_id = type_ids["Projector"]
    projector = conn.execute(
        "SELECT id FROM equipment_units WHERE equipment_type_id = ? ORDER BY id LIMIT 1", (projector_type_id,)
    ).fetchone()
    borrowed_at = datetime.now().replace(microsecond=0).isoformat(sep=" ")
    due_at = (date.today() + timedelta(days=5)).isoformat()
    conn.execute(
        "INSERT INTO rentals (borrower_id, equipment_unit_id, borrowed_at, due_at, deposit, status) VALUES (?, ?, ?, ?, ?, 'active')",
        (borrower_ids["CLUB001"], projector["id"], borrowed_at, due_at, 1500),
    )
    conn.execute("UPDATE equipment_units SET status = 'borrowed' WHERE id = ?", (projector["id"],))
    conn.execute(
        "INSERT INTO reservations (borrower_id, equipment_type_id, quantity, start_date, end_date, status) VALUES (?, ?, ?, ?, ?, 'confirmed')",
        (borrower_ids["CLUB002"], type_ids["DSLR Camera"], 1,
         (date.today() + timedelta(days=10)).isoformat(),
         (date.today() + timedelta(days=12)).isoformat()),
    )


if __name__ == "__main__":
    init_db()
    print(f"Database initialized: {DATABASE}")