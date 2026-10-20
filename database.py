
import sqlite3
from pathlib import Path
from datetime import date

DB_PATH = Path(__file__).resolve().parent / "hotel.db"


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database():
    with connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT UNIQUE NOT NULL,
                room_type TEXT NOT NULL,
                price REAL NOT NULL CHECK(price >= 0),
                capacity INTEGER NOT NULL CHECK(capacity > 0)
            );

            CREATE TABLE IF NOT EXISTS guests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guest_id INTEGER NOT NULL REFERENCES guests(id),
                room_id INTEGER NOT NULL REFERENCES rooms(id),
                check_in TEXT NOT NULL,
                check_out TEXT NOT NULL,
                guest_count INTEGER NOT NULL DEFAULT 1
                    CHECK(guest_count > 0),
                total REAL NOT NULL CHECK(total >= 0),
                status TEXT NOT NULL DEFAULT 'Confirmed'
                    CHECK(status IN ('Confirmed', 'Cancelled')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK(check_out > check_in)
            );

            CREATE INDEX IF NOT EXISTS idx_booking_dates
            ON bookings(room_id, check_in, check_out, status);
        """)


# ---------- ROOMS: CREATE, READ, UPDATE, DELETE ----------

def get_rooms(search=""):
    with connect() as conn:
        return conn.execute("""
            SELECT * FROM rooms
            WHERE number LIKE ? OR room_type LIKE ?
            ORDER BY number
        """, (f"%{search}%", f"%{search}%")).fetchall()


def add_room(number, room_type, price, capacity):
    number = str(number).strip()
    room_type = str(room_type).strip()
    price = float(price)
    capacity = int(capacity)

    if not number or not room_type:
        raise ValueError("Room number and type are required.")
    if not 0 <= price <= 10000000:
        raise ValueError("Enter a valid room price.")
    if not 1 <= capacity <= 20:
        raise ValueError("Capacity must be between 1 and 20.")

    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO rooms(number, room_type, price, capacity)
            VALUES (?, ?, ?, ?)
        """, (number, room_type, price, capacity))
        return cur.lastrowid


def update_room(room_id, number, room_type, price, capacity):
    number = str(number).strip()
    room_type = str(room_type).strip()
    price = float(price)
    capacity = int(capacity)

    if not number or not room_type:
        raise ValueError("Room number and type are required.")
    if not 0 <= price <= 10000000:
        raise ValueError("Enter a valid room price.")
    if not 1 <= capacity <= 20:
        raise ValueError("Capacity must be between 1 and 20.")

    with connect() as conn:
        cur = conn.execute("""
            UPDATE rooms
            SET number=?, room_type=?, price=?, capacity=?
            WHERE id=?
        """, (number, room_type, price, capacity, room_id))

        if cur.rowcount == 0:
            raise ValueError("Room not found.")


def delete_room(room_id):
    with connect() as conn:
        cur = conn.execute("""
            DELETE FROM rooms
            WHERE id=?
            AND NOT EXISTS (
                SELECT 1 FROM bookings
                WHERE bookings.room_id = rooms.id
            )
        """, (room_id,))

        if cur.rowcount == 0:
            raise ValueError(
                "Room not found or has booking history."
            )


# ---------- GUESTS: CRUD ----------

def get_guests(search=""):
    with connect() as conn:
        term = f"%{search}%"
        return conn.execute("""
            SELECT * FROM guests
            WHERE name LIKE ? OR email LIKE ? OR phone LIKE ?
            ORDER BY name
        """, (term, term, term)).fetchall()


def add_guest(name, email, phone="", address=""):
    name = str(name).strip()
    email = str(email).strip().lower()

    if not name or not email or "@" not in email:
        raise ValueError("Enter a guest name and valid email.")

    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO guests(name, email, phone, address)
            VALUES (?, ?, ?, ?)
        """, (
            name, email, str(phone).strip(),
            str(address).strip()
        ))
        return cur.lastrowid


def update_guest(guest_id, name, email, phone="", address=""):
    name = str(name).strip()
    email = str(email).strip().lower()

    if not name or not email or "@" not in email:
        raise ValueError("Enter a guest name and valid email.")

    with connect() as conn:
        cur = conn.execute("""
            UPDATE guests
            SET name=?, email=?, phone=?, address=?
            WHERE id=?
        """, (
            name, email, str(phone).strip(),
            str(address).strip(), guest_id
        ))

        if cur.rowcount == 0:
            raise ValueError("Guest not found.")


def delete_guest(guest_id):
    with connect() as conn:
        cur = conn.execute("""
            DELETE FROM guests
            WHERE id=?
            AND NOT EXISTS (
                SELECT 1 FROM bookings
                WHERE bookings.guest_id = guests.id
            )
        """, (guest_id, guest_id))

        if cur.rowcount == 0:
            raise ValueError(
                "Guest not found or has booking history."
            )


# ---------- BOOKING VALIDATION ----------

def validate_dates(check_in, check_out):
    try:
        start = date.fromisoformat(check_in)
        end = date.fromisoformat(check_out)
    except (TypeError, ValueError):
        raise ValueError("Dates must use YYYY-MM-DD format.")

    if start < date.today():
        raise ValueError("Check-in cannot be in the past.")
    if end <= start:
        raise ValueError("Check-out must be after check-in.")

    return (end - start).days


def available_rooms(check_in, check_out, guest_count=1,
                    exclude_booking_id=None):
    nights = validate_dates(check_in, check_out)
    guest_count = int(guest_count)

    if not 1 <= guest_count <= 20:
        raise ValueError("Enter a valid guest count.")

    params = [guest_count, check_out, check_in]
    exclusion = ""

    if exclude_booking_id is not None:
        exclusion = "AND b.id != ?"
        params.append(exclude_booking_id)

    with connect() as conn:
        return conn.execute(f"""
            SELECT r.* FROM rooms r
            WHERE r.capacity >= ?
            AND NOT EXISTS (
                SELECT 1 FROM bookings b
                WHERE b.room_id = r.id
                AND b.status = 'Confirmed'
                AND b.check_in < ?
                AND b.check_out > ?
                {exclusion}
            )
            ORDER BY r.price
        """, params).fetchall()


# ---------- BOOKINGS: CREATE, READ, UPDATE, CANCEL ----------

def create_booking(guest_id, room_id, check_in, check_out,
                   guest_count=1):
    nights = validate_dates(check_in, check_out)
    guest_count = int(guest_count)

    if not 1 <= guest_count <= 20:
        raise ValueError("Enter a valid guest count.")

    # BEGIN IMMEDIATE obtains a write reservation before checking
    # availability, reducing the risk of overlapping concurrent writes.
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")

        room = conn.execute(
            "SELECT * FROM rooms WHERE id=?", (room_id,)
        ).fetchone()
        guest = conn.execute(
            "SELECT id FROM guests WHERE id=?", (guest_id,)
        ).fetchone()

        if room is None or guest is None:
            raise ValueError("Select an existing room and guest.")
        if guest_count > room["capacity"]:
            raise ValueError("Guest count exceeds room capacity.")

        conflict = conn.execute("""
            SELECT id FROM bookings
            WHERE room_id=? AND status='Confirmed'
            AND check_in < ? AND check_out > ?
        """, (room_id, check_out, check_in)).fetchone()

        if conflict:
            raise ValueError("Room is unavailable for these dates.")

        total = round(room["price"] * nights, 2)
        cur = conn.execute("""
            INSERT INTO bookings
            (guest_id, room_id, check_in, check_out,
             guest_count, total, status)
            VALUES (?, ?, ?, ?, ?, ?, 'Confirmed')
        """, (
            guest_id, room_id, check_in, check_out,
            guest_count, total
        ))
        return cur.lastrowid


def get_bookings(search=""):
    term = f"%{search}%"

    with connect() as conn:
        return conn.execute("""
            SELECT b.id, b.guest_id, b.room_id,
                   g.name AS guest, r.number AS room,
                   b.check_in, b.check_out, b.guest_count,
                   b.total, b.status, b.created_at
            FROM bookings b
            JOIN guests g ON g.id=b.guest_id
            JOIN rooms r ON r.id=b.room_id
            WHERE g.name LIKE ? OR r.number LIKE ?
               OR CAST(b.id AS TEXT) LIKE ?
            ORDER BY b.id DESC
        """, (term, term, term)).fetchall()


def update_booking(booking_id, guest_id, room_id,
                   check_in, check_out, guest_count=1):
    nights = validate_dates(check_in, check_out)
    guest_count = int(guest_count)

    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")

        room = conn.execute(
            "SELECT * FROM rooms WHERE id=?", (room_id,)
        ).fetchone()
        guest = conn.execute(
            "SELECT id FROM guests WHERE id=?", (guest_id,)
        ).fetchone()
        booking = conn.execute(
            "SELECT status FROM bookings WHERE id=?", (booking_id,)
        ).fetchone()

        if room is None or guest is None or booking is None:
            raise ValueError("Booking, room or guest not found.")
        if booking["status"] != "Confirmed":
            raise ValueError("Only confirmed bookings can be edited.")
        if not 1 <= guest_count <= room["capacity"]:
            raise ValueError("Guest count exceeds room capacity.")

        conflict = conn.execute("""
            SELECT id FROM bookings
            WHERE room_id=? AND id != ? AND status='Confirmed'
            AND check_in < ? AND check_out > ?
        """, (room_id, booking_id, check_out, check_in)).fetchone()

        if conflict:
            raise ValueError("Room is unavailable for these dates.")

        conn.execute("""
            UPDATE bookings
            SET guest_id=?, room_id=?, check_in=?, check_out=?,
                guest_count=?, total=?
            WHERE id=?
        """, (
            guest_id, room_id, check_in, check_out,
            guest_count, round(room["price"] * nights, 2),
            booking_id
        ))


def cancel_booking(booking_id):
    with connect() as conn:
        cur = conn.execute("""
            UPDATE bookings SET status='Cancelled'
            WHERE id=? AND status='Confirmed'
        """, (booking_id,))

        if cur.rowcount == 0:
            raise ValueError("Confirmed booking not found.")


# ---------- DASHBOARD ----------

def get_dashboard_stats():
    with connect() as conn:
        return {
            "rooms": conn.execute(
                "SELECT COUNT(*) FROM rooms"
            ).fetchone()[0],
            "guests": conn.execute(
                "SELECT COUNT(*) FROM guests"
            ).fetchone()[0],
            "bookings": conn.execute(
                """SELECT COUNT(*) FROM bookings
                   WHERE status='Confirmed'"""
            ).fetchone()[0],
            "revenue": conn.execute(
                """SELECT COALESCE(SUM(total), 0)
                   FROM bookings WHERE status='Confirmed'"""
            ).fetchone()[0]
        }


if __name__ == "__main__":
    initialize_database()
    print("Database initialized:", DB_PATH)
