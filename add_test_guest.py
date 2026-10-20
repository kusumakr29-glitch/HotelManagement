
import database

database.initialize_database()

guest_id = database.add_guest(
    "Test Guest",
    "testguest@example.com",
    "9876543210",
    "Bengaluru"
)

print("Guest created successfully!")
print("Guest ID:", guest_id)
