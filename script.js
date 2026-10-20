"use strict";

const API = "/api";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

let rooms = [];
let selectedRoom = null;
let toastTimer = null;

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    throw new Error(
      typeof data === "object" && data !== null
        ? data.error || data.message || "Request failed"
        : data || "Request failed"
    );
  }

  return data;
}

function showToast(message) {
  const toast = $("#toast");

  if (!toast) {
    alert(message);
    return;
  }

  toast.textContent = message;
  toast.style.display = "block";

  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.style.display = "none";
  }, 3500);
}

function money(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0
  }).format(Number(value) || 0);
}

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[character]);
}

function localDateString() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function nightsBetween(checkIn, checkOut) {
  if (!checkIn || !checkOut) return 0;

  const start = new Date(`${checkIn}T00:00:00`);
  const end = new Date(`${checkOut}T00:00:00`);

  return Math.round((end - start) / 86400000);
}

function getRoomId(room) {
  return room.id ?? room.room_id;
}

function getRoomNumber(room) {
  return room.room_number ?? room.room_no ?? room.number ?? "";
}

function getRoomType(room) {
  return room.room_type ?? room.type ?? "Standard";
}

function getRoomPrice(room) {
  return Number(room.price_per_night ?? room.price ?? 0);
}

function getRoomCapacity(room) {
  return Number(room.capacity ?? 1);
}

function renderRooms(roomList = rooms) {
  const grid = $("#roomGrid");
  const emptyMessage = $("#noRooms");

  if (!grid) return;

  if (roomList.length === 0) {
    grid.innerHTML = "";
    emptyMessage?.classList.remove("hidden");
    return;
  }

  emptyMessage?.classList.add("hidden");

  grid.innerHTML = roomList.map((room) => {
    const id = getRoomId(room);
    const number = getRoomNumber(room);
    const type = getRoomType(room);
    const price = getRoomPrice(room);
    const capacity = getRoomCapacity(room);

    return `
      <article class="room-card"
        data-type="${escapeHTML(type.toLowerCase())}"
        data-capacity="${capacity}">
        <div class="room-image">
          <img src="https://images.unsplash.com/photo-1611892440504-42a792e24d32?auto=format&fit=crop&w=1000&q=80"
               alt="Hotel room" loading="lazy">
          <span class="badge">${escapeHTML(type)}</span>
        </div>
        <div class="room-body">
          <p class="category">${escapeHTML(type.toUpperCase())} · ${capacity} GUEST(S)</p>
          <h3>${escapeHTML(type)} Room ${escapeHTML(number)}</h3>
          <p>A comfortable room with thoughtful amenities.</p>
          <div class="room-bottom">
            <span><strong>${money(price)}</strong> / night</span>
            <button type="button" class="book-room"
              data-room-id="${escapeHTML(id)}">Book room ↗</button>
          </div>
        </div>
      </article>`;
  }).join("");
}

async function loadRooms() {
  try {
    const result = await apiRequest("/rooms");
    rooms = Array.isArray(result) ? result : result.rooms || [];
    renderRooms();
    applyRoomFilter();
  } catch (error) {
    console.error(error);
    showToast("Unable to load rooms. Check your Python server.");
  }
}

function applyRoomFilter() {
  const filter = $("#roomFilter");
  if (!filter) return;

  const type = filter.value.toLowerCase();

  const filtered = type === "all"
    ? rooms
    : rooms.filter((room) => {
        const roomType = getRoomType(room).toLowerCase();

        if (type === "standard") {
          return roomType.includes("standard") ||
                 roomType.includes("classic");
        }

        if (type === "deluxe") {
          return roomType.includes("deluxe") ||
                 roomType.includes("premium");
        }

        if (type === "suite") {
          return roomType.includes("suite");
        }

        return roomType === type;
      });

  renderRooms(filtered);
}

async function searchAvailability(event) {
  event.preventDefault();

  const checkIn = $("#checkIn")?.value;
  const checkOut = $("#checkOut")?.value;
  const guests = Number($("#guestCount")?.value || 1);
  const message = $("#searchMessage");

  if (!checkIn || !checkOut ||
      nightsBetween(checkIn, checkOut) <= 0 ||
      checkIn < localDateString()) {
    if (message) {
      message.textContent = "Please select valid check-in and check-out dates.";
    }
    return;
  }

  if (message) message.textContent = "Checking availability...";

  try {
    const query = new URLSearchParams({
      check_in: checkIn,
      check_out: checkOut,
      guests: String(guests)
    });

    const result = await apiRequest(`/availability?${query}`);
    rooms = Array.isArray(result) ? result : result.rooms || [];
    renderRooms(rooms);

    if (message) {
      message.textContent = rooms.length
        ? `${rooms.length} available room(s) found.`
        : "No rooms available for these dates.";
    }

    $("#rooms")?.scrollIntoView({ behavior: "smooth" });
  } catch (error) {
    console.error(error);
    if (message) message.textContent = error.message;
  }
}

function updateEstimate() {
  const estimate = $("#estimate");
  if (!estimate || !selectedRoom) return;

  const nights = nightsBetween($("#modalIn")?.value, $("#modalOut")?.value);

  estimate.textContent = nights > 0
    ? `${money(nights * getRoomPrice(selectedRoom))} (${nights} nights)`
    : "Choose valid dates";
}

function openBookingDialog(roomId) {
  const room = rooms.find(
    (item) => String(getRoomId(item)) === String(roomId)
  );

  if (!room) {
    showToast("Room not found.");
    return;
  }

  selectedRoom = room;

  const dialog = $("#bookingDialog");
  if (!dialog) {
    showToast("Booking dialog is missing from index.html.");
    return;
  }

  $("#selectedRoom").textContent =
    `${getRoomType(room)} Room ${getRoomNumber(room)} — ${money(getRoomPrice(room))} per night`;

  $("#roomBookingForm")?.classList.remove("hidden");
  $("#bookingSuccess")?.classList.add("hidden");
  $("#roomBookingForm")?.reset();

  $("#modalIn").value = $("#checkIn")?.value || localDateString();
  $("#modalOut").value = $("#checkOut")?.value || "";

  const guests = $("#modalGuests");
  if (guests) {
    guests.innerHTML = Array.from(
      { length: Math.max(1, getRoomCapacity(room)) },
      (_, i) => `<option value="${i + 1}">${i + 1} guest(s)</option>`
    ).join("");

    guests.value = String(Math.min(
      Number($("#guestCount")?.value || 1),
      getRoomCapacity(room)
    ));
  }

  updateEstimate();

  if (!dialog.open) dialog.showModal();
}

function closeBookingDialog() {
  const dialog = $("#bookingDialog");
  if (dialog?.open) dialog.close();
}



async function createBooking(event) {
  event.preventDefault();

  if (!selectedRoom) {
    showToast("Please select a room.");
    return;
  }

  const guestName = $("#guestName").value.trim();
  const guestEmail = $("#guestEmail").value.trim();
  const checkIn = $("#modalIn").value;
  const checkOut = $("#modalOut").value;
  const guestCount = Number($("#modalGuests").value);

  if (!guestName || !guestEmail || !checkIn || !checkOut) {
    showToast("Please complete all fields.");
    return;
  }

  if (
    checkIn < localDateString() ||
    nightsBetween(checkIn, checkOut) <= 0
  ) {
    showToast("Please select valid dates.");
    return;
  }

  if (guestCount > getRoomCapacity(selectedRoom)) {
    showToast("Too many guests for this room.");
    return;
  }

  try {
    // Find the guest using their email address.
    const guests = await apiRequest(
      `/guests?search=${encodeURIComponent(guestEmail)}`
    );
    console.log("Guests returned by API:", guests);
    console.log("Selected room:", selectedRoom);
    console.log("Room ID:", getRoomId(selectedRoom));

    let guest = guests.find(
      item =>
        item.email?.toLowerCase() === guestEmail.toLowerCase()
    );

    // Register the guest if they don't already exist.
    if (!guest) {
      guest = await apiRequest("/guests", {
        method: "POST",
        body: JSON.stringify({
          name: guestName,
          email: guestEmail,
          phone: "",
          address: ""
        })
      });
    }

    const guestId = guest.id;
    const roomId = getRoomId(selectedRoom);

    if (guestId == null || roomId == null) {
      throw new Error("Guest ID or room ID is missing.");
    }

    // Send the fields expected by server.py.
    const result = await apiRequest("/bookings", {
      method: "POST",
      body: JSON.stringify({
        guest_id: guestId,
        room_id: roomId,
        check_in: checkIn,
        check_out: checkOut,
        guest_count: guestCount
      })
    });

    $("#roomBookingForm").classList.add("hidden");

    const success = $("#bookingSuccess");
    success.classList.remove("hidden");
    success.textContent =
      `Booking confirmed! Reference: ${result.id}`;

    showToast("Booking created successfully.");

    await loadDashboard();

  } catch (error) {
    console.error("Booking failed:", error);
    showToast(error.message || "Booking failed.");
  }
}


async function loadDashboard() {
  try {
    const data = await apiRequest("/dashboard");

    const totalRooms = $("#totalRooms");
    const totalBookings = $("#totalBookings");
    const occupancy = $("#occupancyRate");
    const revenue = $("#revenueEstimate");

    if (totalRooms && data.total_rooms != null) {
      totalRooms.textContent = data.total_rooms;
    }

    if (totalBookings && data.total_bookings != null) {
      totalBookings.textContent = data.total_bookings;
    }

    if (occupancy && data.occupancy_rate != null) {
      occupancy.textContent = `${data.occupancy_rate}%`;
    }

    if (revenue && data.total_revenue != null) {
      revenue.textContent = money(data.total_revenue);
    }
  } catch (error) {
    console.warn("Dashboard API unavailable:", error.message);
  }
}

function setupDateInputs() {
  const today = localDateString();

  ["#checkIn", "#checkOut", "#modalIn", "#modalOut"].forEach((selector) => {
    const input = $(selector);
    if (input) input.min = today;
  });

  $("#modalIn")?.addEventListener("change", () => {
    const checkOut = $("#modalOut");
    if (checkOut) checkOut.min = $("#modalIn").value || today;
    updateEstimate();
  });

  $("#modalOut")?.addEventListener("change", updateEstimate);
}

function setupNavigation() {
  const toggle = $("#menuToggle");
  const navigation = $("#navigation");

  toggle?.addEventListener("click", () => {
    const open = navigation?.classList.toggle("open");
    toggle.setAttribute("aria-expanded", String(Boolean(open)));
  });

  $$(".nav-link, .nav-cta").forEach((link) => {
    link.addEventListener("click", () => {
      navigation?.classList.remove("open");
      toggle?.setAttribute("aria-expanded", "false");
    });
  });
}

function setupTestimonials() {
  const reviews = [
    {
      text: "A beautiful room, kind people and the calm you did not know you needed.",
      name: "Nisha P.",
      location: "Chennai, India"
    },
    {
      text: "Comfortable rooms and friendly staff made our stay memorable.",
      name: "Rahul M.",
      location: "Mysuru, India"
    },
    {
      text: "A peaceful stay with thoughtful details and a lovely atmosphere.",
      name: "Ananya R.",
      location: "Hyderabad, India"
    }
  ];

  let index = 0;

  function displayReview(next) {
    index = (next + reviews.length) % reviews.length;
    const review = reviews[index];

    if ($("#quoteText")) $("#quoteText").textContent = `“${review.text}”`;
    if ($("#quoteName")) $("#quoteName").textContent = review.name;
    if ($("#quoteLocation")) $("#quoteLocation").textContent = review.location;
  }

  $("#prevQuote")?.addEventListener("click", () => displayReview(index - 1));
  $("#nextQuote")?.addEventListener("click", () => displayReview(index + 1));
}

function setupEvents() {
  $("#bookingForm")?.addEventListener("submit", searchAvailability);
  $("#roomFilter")?.addEventListener("change", applyRoomFilter);

  $("#roomGrid")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-room-id]");
    if (button) openBookingDialog(button.dataset.roomId);
  });

  $("#closeDialog")?.addEventListener("click", closeBookingDialog);
  $("#roomBookingForm")?.addEventListener("submit", createBooking);

  $("#modalIn")?.addEventListener("change", updateEstimate);
  $("#modalOut")?.addEventListener("change", updateEstimate);

  $("#contactForm")?.addEventListener("submit", (event) => {
    event.preventDefault();

    const message = $("#contactMessage");
    if (message) {
      message.textContent =
        "Thank you! This demonstration does not send emails.";
    }

    event.target.reset();
  });

  $("#bookingDialog")?.addEventListener("click", (event) => {
    if (event.target === $("#bookingDialog")) closeBookingDialog();
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  setupDateInputs();
  setupNavigation();
  setupTestimonials();
  setupEvents();

  await loadRooms();
  await loadDashboard();

  console.log("Grand Haven Hotel Management System initialized.");
});
