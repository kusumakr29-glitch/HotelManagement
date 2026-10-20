
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import database as db

BASE_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8000


class HotelHandler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def send_json(self, status, data):
        def normalize(value):
            if isinstance(value, sqlite3.Row):
                return dict(value)
            if isinstance(value, list):
                return [normalize(item) for item in value]
            if isinstance(value, dict):
                return {
                    key: normalize(item)
                    for key, item in value.items()
                }
            return value

        body = json.dumps(normalize(data)).encode("utf-8")
        self.send_response(status)
        self.send_header(
            "Content-Type", "application/json; charset=utf-8"
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))

        if length <= 0 or length > 100_000:
            raise ValueError(
                "Request body is missing or too large."
            )

        data = json.loads(
            self.rfile.read(length).decode("utf-8")
        )

        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object.")

        return data

    def handle_api(self, method):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        def param(name, default=""):
            return query.get(name, [default])[0]

        # GET endpoints
        if method == "GET":
            if path == "/api/rooms":
                return db.get_rooms(param("search"))

            if path == "/api/guests":
                return db.get_guests(param("search"))

            # if path == "/api/bookings":
            #     return db.get_bookings(param("search"))
            if path == "/api/bookings":
                print("Booking request received:", data)
                print("Available room IDs:",
                    [room["id"] for room in db.get_rooms()])
                print("Available guest IDs:",
                    [guest["id"] for guest in db.get_guests()])

                new_id = db.create_booking(
                    data.get("guest_id"),
                    data.get("room_id"),
                    data.get("check_in", ""),
                    data.get("check_out", ""),
                    data.get("guest_count", 1)
                )

                return {
                    "id": new_id,
                    "message": "Booking created."
                }

            if path == "/api/dashboard":
                return db.get_dashboard_stats()

            if path == "/api/availability":
                check_in = param("check_in")
                check_out = param("check_out")
                guests = int(param("guests", "1"))

                if not check_in or not check_out:
                    raise ValueError(
                        "Check-in and check-out dates are required."
                    )

                if guests < 1:
                    raise ValueError(
                        "Guest count must be at least 1."
                    )

                rooms = db.available_rooms(
                    check_in, check_out, guests
                )
                return [dict(room) for room in rooms]

        # POST endpoints
        if method == "POST":
            data = self.read_json()

            if path == "/api/rooms":
                new_id = db.add_room(
                    data.get("number", ""),
                    data.get("room_type", ""),
                    data.get("price", 0),
                    data.get("capacity", 1)
                )
                return {"id": new_id, "message": "Room added."}

            if path == "/api/guests":
                new_id = db.add_guest(
                    data.get("name", ""),
                    data.get("email", ""),
                    data.get("phone", ""),
                    data.get("address", "")
                )
                return {"id": new_id, "message": "Guest added."}

            if path == "/api/bookings":
                new_id = db.create_booking(
                    data.get("guest_id"),
                    data.get("room_id"),
                    data.get("check_in", ""),
                    data.get("check_out", ""),
                    data.get("guest_count", 1)
                )
                return {
                    "id": new_id,
                    "message": "Booking created."
                }

        # PUT and DELETE endpoints
        parts = path.strip("/").split("/")

        if method == "PUT" and len(parts) == 3:
            resource = parts[1]
            record_id = int(parts[2])
            data = self.read_json()

            if resource == "rooms":
                db.update_room(
                    record_id,
                    data.get("number", ""),
                    data.get("room_type", ""),
                    data.get("price", 0),
                    data.get("capacity", 1)
                )
                return {"message": "Room updated."}

            if resource == "guests":
                db.update_guest(
                    record_id,
                    data.get("name", ""),
                    data.get("email", ""),
                    data.get("phone", ""),
                    data.get("address", "")
                )
                return {"message": "Guest updated."}

            if resource == "bookings":
                db.update_booking(
                    record_id,
                    data.get("guest_id"),
                    data.get("room_id"),
                    data.get("check_in", ""),
                    data.get("check_out", ""),
                    data.get("guest_count", 1)
                )
                return {"message": "Booking updated."}

        if method == "DELETE" and len(parts) == 3:
            resource = parts[1]
            record_id = int(parts[2])

            if resource == "rooms":
                db.delete_room(record_id)
                return {"message": "Room deleted."}

            if resource == "guests":
                db.delete_guest(record_id)
                return {"message": "Guest deleted."}

            if resource == "bookings":
                db.cancel_booking(record_id)
                return {"message": "Booking cancelled."}

        raise LookupError("API endpoint not found.")

    def do_GET(self):
        if urlparse(self.path).path.startswith("/api/"):
            self.process_api("GET")
        else:
            super().do_GET()

    def do_POST(self):
        self.process_api("POST")

    def do_PUT(self):
        self.process_api("PUT")

    def do_DELETE(self):
        self.process_api("DELETE")

    def process_api(self, method):
        try:
            result = self.handle_api(method)
            self.send_json(200, result)

        except LookupError as exc:
            self.send_json(404, {"error": str(exc)})

        except (
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError
        ) as exc:
            self.send_json(400, {"error": str(exc)})

        except Exception as exc:
            self.log_error("API error: %s", exc)
            self.send_json(
                500, {"error": "Internal server error."}
            )


if __name__ == "__main__":
    db.initialize_database()

    server = ThreadingHTTPServer(
        (HOST, PORT), HotelHandler
    )

    print(f"Grand Haven running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop the server.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()
