# Smart Campus Matrix

Smart Campus Matrix is a campus-navigation and room-status app built with a **FastAPI** backend, **SQLite** database, and a **Progressive Web App (PWA)** frontend that can be installed on Android phones.

> **Now a PWA!** Install it on your Android phone like a native app.

---

## Features

- **Live Room Dashboard** — Real-time room availability cards with timetable-aware status (AVAILABLE / BUSY)
- **Search Bar** — Filter rooms by name, status, or schedule text on the dashboard
- **Filter Buttons** — Quick filter: All, Scheduled, Occupied, Empty
- **Campus Map & Navigation** — Leaflet-based interactive map with GPS tracking and route planning between campus nodes
- **CCTV Live View** — Supports HLS (.m3u8), RTSP (VLC), MJPEG (IP Webcam), YouTube Live, and HTTP streams per room
- **Student Portal** — Registration, login, personal schedule lookup
- **Admin Panel** — Room override controls, timetable management (PDF upload + manual entry), campus node manager (add/delete nodes, set CCTV URLs)
- **Timetable Parser** — Upload any PDF timetable; the system auto-detects day columns, time slots, course codes, and venues
- **PWA Ready** — Install on Android as a standalone app, works with GPS and CCTV from your phone

---

## Requirements

- **Python 3.10+**
- **pip**
- Internet connection (for Leaflet map tiles, Font Awesome icons, HLS.js)

---

## Quick Start (Local Development)

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the server (database is auto-setup on first run)
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Then open **http://127.0.0.1:8000** in your browser.

If you want to use it on your phone, find your PC's local IP with `ipconfig` and open `http://YOUR_IP:8000` on your phone (must be on the same WiFi network).

---

## Installing on Android (PWA)

The app is now a **Progressive Web App**. To install it on your Android phone:

### Step 1: Host the Backend Online
The backend must be accessible from your phone. You can:

**Option A: Free Cloud Hosting (Recommended)**
- Deploy `main.py` to [Render.com](https://render.com), [PythonAnywhere](https://pythonanywhere.com), or [Railway.app](https://railway.app)
- These services offer free tiers that can run the FastAPI backend 24/7

**Option B: Local Network (for testing)**
- Find your PC's local IP: Run `ipconfig` and look for `IPv4 Address` (e.g., `192.168.1.100`)
- Start the server: `uvicorn main:app --host 0.0.0.0 --port 8000`
- Update `API_URL` in `app.html` to your PC's IP: `http://192.168.1.100:8000`
- Connect your phone to the same WiFi network

### Step 2: Open the App on Your Phone
- Open Chrome on your Android phone
- Navigate to the app URL shown by `setup_and_run.py` or your hosted backend URL
- Chrome will show an **"Add to Home Screen"** banner
- Tap it — the app installs like a native app!

### Step 2b: Use It Like a Mobile App
- After installation, open it from the home screen icon
- The app runs in standalone mode and keeps the phone-friendly layout

### Step 3: Using GPS & CCTV
- GPS works automatically when you grant location permission
- CCTV (IP Webcam): Install IP Webcam app on another phone, start the server, enter the MJPEG URL (e.g., `http://192.168.1.101:8080/video`) in the Admin panel's Node Manager

---

## How to Use

### Dashboard (Default View)
- View all rooms with live status (AVAILABLE / BUSY)
- **Search bar** — type any room name, status, or schedule keyword
- **Filter buttons** — All / Scheduled / Occupied / Empty
- Click **"Live CCTV"** on any room card to view its camera feed (if configured)

### Map Routes
- Navigate to the **Map** tab from the bottom nav
- Select a start point (or use "My Live GPS Location") and a destination
- Click **"Start Live Guidance"** to see the route on the map

### Student Login / Registration
- Click **"Open Account Portal"** at the top
- **Create New Account** — fill in reg no, password, course, year, semester, and select your enrolled units
- **Login as Student** — view your personal class schedule

### Admin Panel
- Login as Admin using your username and password
- If you need to create an admin account, use one of these 4-digit OTPs first:
	- `1024`
	- `2048`
	- `3141`
	- `4286`
	- `5369`
	- `6420`
	- `7531`
	- `8642`
	- `9753`
	- `1089`
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

...and more admin endpoints for timetable and node management.

---

## Project Files

| File | Description |
|------|-------------|
| `main.py` | FastAPI backend — all API routes and business logic |
| `app.html` | PWA frontend (installable on Android) |
| `setup_and_run.py` | One-command setup: creates DB tables, seeds data, starts server |
| `static/manifest.json` | PWA manifest (name, icons, theme, display mode) |
| `static/sw.js` | Service worker (offline support, caching) |
| `static/icons/` | PWA app icons (192x192, 512x512) |
| `seed_campus_map.py` | Seeds campus nodes (28 locations) and edges (31 pathways) |
| `database_setup.py` | Creates the required database tables |
| `requirements.txt` | Python dependencies |
| `campus_navigation.db` | SQLite database (auto-created) |

---

## Troubleshooting

- **"No such table" error** — Run `python setup_and_run.py` or `python database_setup.py` to create missing tables.
- **Frontend can't reach backend** — Confirm the API is running on the correct URL. Check the server terminal for errors.
- **PWA not installing** — The app must be served via HTTP/HTTPS (not `file://`). Host it online or use a local server.
- **Map not loading** — Ensure you have internet access (Leaflet tiles are loaded from OpenStreetMap).
- **GPS not working** — The app falls back to a default campus location if GPS is unavailable or outside campus range.
- **Admin login** — Default shared admin login is `admin` / `Campus@123`. You can also create OTP-gated admin accounts using the 4-digit codes listed in the Admin Panel section.
- **CCTV not loading (IP Webcam)** — Use the MJPEG URL format: `http://[phone-ip]:8080/video`. Both devices must be on the same network.