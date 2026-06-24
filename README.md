# Smart Campus Matrix

Smart Campus Matrix is a campus-navigation and room-status app built with a **FastAPI** backend, **SQLite** database, and a mobile-style static frontend (`app.html`).

---

## Features

- **Live Room Dashboard** — Real-time room availability cards with timetable-aware status (AVAILABLE / BUSY)
- **Search Bar** — Filter rooms by name, status, or schedule text on the dashboard
- **Filter Buttons** — Quick filter: All, Scheduled, Occupied, Empty
- **Campus Map & Navigation** — Leaflet-based interactive map with GPS tracking and route planning between campus nodes
- **CCTV Live View** — Supports HLS (.m3u8), RTSP (VLC), YouTube Live, and HTTP streams per room
- **Student Portal** — Registration, login, personal schedule lookup
- **Admin Panel** — Room override controls, timetable management (PDF upload + manual entry), campus node manager (add/delete nodes, set CCTV URLs)
- **Timetable Parser** — Upload any PDF timetable; the system auto-detects day columns, time slots, course codes, and venues

---

## Requirements

- **Python 3.10+**
- **pip**
- Internet connection (for Leaflet map tiles, Font Awesome icons, HLS.js)

---

## Quick Start (One-Command Setup)

From the repository root:

```powershell
# 1. Clone the repo
git clone https://github.com/Franco3291/Hall-master.git
cd Hall-master

# 2. (Optional) Create a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run everything (database setup + server start)
python setup_and_run.py
```

This single command will:
- Create all required database tables (nodes, edges, timetable, students)
- Seed the campus map with 28 nodes and 31 pathway edges (if first run)
- Start the FastAPI server on `http://127.0.0.1:8000`

Then open **`app.html`** in your browser.

---

## Manual Setup (Step by Step)

### 1. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 2. Initialize the Database

```powershell
python setup_and_run.py
```

Or run the individual scripts:

```powershell
python database_setup.py          # Create tables
python create_students_table.py   # Ensure students table exists
python seed_campus_map.py         # Seed nodes & edges (optional, refreshes data)
```

### 3. Start the Backend Server

```powershell
set ADMIN_PASSWORD=Campus@123
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 4. Open the Frontend

Open **`app.html`** in any modern browser (Chrome, Edge, Firefox).

---

## How to Use

### Dashboard (Default View)
- View all rooms with live status (AVAILABLE / BUSY)
- **Search bar** — type any room name, status, or schedule keyword
- **Filter buttons** — All / Scheduled / Occupied / Empty
- Click **"📹 Live CCTV"** on any room card to view its camera feed (if configured)

### Map Routes
- Navigate to the **Map** tab from the bottom nav
- Select a start point (or use "My Live GPS Location") and a destination
- Click **"Start Live Guidance"** to see the route on the map

### Student Login / Registration
- Click **"Open Account Portal"** at the top
- **Create New Account** — fill in reg no, password, course, year, semester, and select your enrolled units
- **Login as Student** — view your personal class schedule

### Admin Panel
- Login as Admin (password: `Campus@123`)
- **Room Override** — manually set rooms ACTIVE or INACTIVE
- **Timetable Management** — upload a PDF timetable or add entries manually
- **Campus Node Manager** — add/delete nodes, set CCTV camera URLs for each room

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server health check with DB counts |
| GET | `/rooms/status` | Live room availability feed |
| GET | `/api/geo-nodes` | All campus nodes with GPS coordinates & camera URLs |
| POST | `/students/register` | Register a new student |
| POST | `/students/login` | Student login |
| GET | `/students/available-units` | Get available course units (filtered by course/year/semester) |
| GET | `/students/schedule/{reg_no}` | Get student's personal schedule |
| POST | `/admin/login` | Admin authentication |
| POST | `/verify` | Set room occupancy status (admin override) |
| POST | `/rooms/reset` | Reset all room overrides |
| POST | `/navigate` | Calculate shortest path between two nodes |
| POST | `/admin/timetable/upload-pdf` | Upload & parse a PDF timetable |
| GET | `/admin/timetable/all` | View all timetable entries |
| POST | `/admin/timetable/add` | Add a timetable entry |
| PUT | `/admin/timetable/update/{id}` | Update a timetable entry |
| DELETE | `/admin/timetable/delete/{id}` | Delete a timetable entry |
| DELETE | `/admin/timetable/clear` | Clear all timetable entries |
| GET | `/admin/nodes/all` | View all campus nodes |
| POST | `/admin/nodes/add` | Add a new campus node |
| PUT | `/admin/nodes/update/{name}` | Update a node |
| DELETE | `/admin/nodes/delete/{name}` | Delete a node |
| POST | `/admin/nodes/camera/{name}` | Set CCTV camera URL for a node |

---

## Project Files

| File | Description |
|------|-------------|
| `main.py` | FastAPI backend — all API routes and business logic |
| `app.html` | Single-page frontend (mobile-style UI) |
| `setup_and_run.py` | One-command setup: creates DB tables, seeds data, starts server |
| `seed_campus_map.py` | Seeds campus nodes (28 locations) and edges (31 pathways) |
| `database_setup.py` | Creates the required database tables |
| `create_students_table.py` | Ensures the students table exists |
| `cctv_fix.py` | Reference file for CCTV/HLS integration |
| `requirements.txt` | Python dependencies |
| `campus_navigation.db` | SQLite database (auto-created) |

---

## Troubleshooting

- **"No such table" error** — Run `python setup_and_run.py` or `python database_setup.py` to create missing tables.
- **Frontend can't reach backend** — Confirm the API is running on `http://127.0.0.1:8000`. Check the server terminal for errors.
- **Map not loading** — Ensure you have internet access (Leaflet tiles are loaded from OpenStreetMap).
- **GPS not working** — The app falls back to a default campus location if GPS is unavailable or outside campus range.
- **Admin password** — Default is `Campus@123`. Override with `set ADMIN_PASSWORD=yourpassword` before starting the server.
- **PDF upload fails** — Check the server terminal for parsing details. The PDF must contain a table with day names (Monday-Saturday) and time ranges (e.g., "08:00-10:00").

---

## Notes

- Run all commands from the repository root so the app opens the correct `campus_navigation.db` file.
- The frontend uses browser geolocation and Leaflet tiles, so it works best with internet access enabled.
- CCTV supports: HLS streams (`.m3u8`), RTSP (opens in VLC), YouTube Live, and generic HTTP/HTTPS embed URLs.