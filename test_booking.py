
import database

rooms = database.get_rooms()
guests = database.get_guests("testguest@example.com")

print("Rooms:", [dict(room) for room in rooms])
print("Guests:", [dict(guest) for guest in guests])

if rooms and guests:
    try:
        booking_id = database.create_booking(
            guest_id=guests[0]["id"],
            room_id=rooms[0]["id"],
            check_in="2026-11-01",
            check_out="2026-11-03",
            guest_count=1
        )
        print("Booking created! ID:", booking_id)
    except Exception as error:
        print("Booking failed:", error)
else:
    print("Room or guest is missing.")
