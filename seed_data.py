
import database as db

db.initialize_database()

if not db.get_rooms():
    sample_rooms = [
        ("101", "Standard", 2200, 1),
        ("201", "Deluxe", 3500, 2),
        ("202", "Deluxe", 3900, 2),
        ("301", "Suite", 6800, 4),
        ("401", "Family", 5200, 4),
        ("501", "Suite", 7500, 3),
    ]

    for number, room_type, price, capacity in sample_rooms:
        db.add_room(number, room_type, price, capacity)

    print("Sample rooms inserted.")

else:
    print("Rooms already exist; no data inserted.")
