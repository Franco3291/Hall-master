import os
import re
import sys
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime
from contextlib import contextmanager
import shutil

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Campus@123')
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///campus_navigation.db')
USE_POSTGRES = DATABASE_URL.startswith('postgres')

from starlette.responses import FileResponse

# 1. Initialize the FastAPI application instance
app = FastAPI()

@app.get("/")
def serve_frontend():
    """Serve the main frontend application."""
    return FileResponse("app.html")

# 2. Enable CORS so app.html can communicate with this backend smoothly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up storage for uploaded images and PDFs
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

    @contextmanager
    def get_db():
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        try:
            yield conn
        finally:
            conn.close()

    def dict_fetchall(cursor):
        """Convert psycopg2 cursor results to list of dicts."""
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def dict_fetchone(cursor):
        """Convert psycopg2 cursor result to a single dict."""
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        row = cursor.fetchone()
        if row:
            return dict(zip(columns, row))
        return None

    # ─── PostgreSQL-specific helpers ────────────────────────────────────────
    PG_TYPE_MAP = {
        'TEXT': 'TEXT',
        'INTEGER': 'INTEGER',
        'REAL': 'DOUBLE PRECISION',
        'AUTOINCREMENT': 'SERIAL',
    }

    def pg_type(sqlite_type):
        return PG_TYPE_MAP.get(sqlite_type, sqlite_type)

    SQLITE_TO_PG = {
        'AUTOINCREMENT': 'SERIAL',
    }

    def translate_ddl(sql: str) -> str:
        """Translate SQLite DDL to PostgreSQL-compatible DDL."""
        sql = sql.replace("AUTOINCREMENT", "SERIAL")
        sql = sql.replace("IF NOT EXISTS", "IF NOT EXISTS")
        # Remove double quotes from string literals used as defaults
        return sql

    def adapt_params(query: str, params: tuple) -> tuple:
        """Convert ? placeholders to %s for psycopg2."""
        return query.replace('?', '%s')

else:
    import sqlite3

    @contextmanager
    def get_db():
        conn = sqlite3.connect('campus_navigation.db')
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def dict_fetchall(cursor):
        return [dict(row) for row in cursor.fetchall()]

    def dict_fetchone(cursor):
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def adapt_params(query: str, params: tuple) -> tuple:
        return query  # SQLite uses ? directly


def execute(conn, sql: str, params=None):
    """Execute a query with automatic ? → %s conversion for PostgreSQL."""
    if params is None:
        params = ()
    cur = conn.cursor()
    cur.execute(adapt_params(sql, params) if USE_POSTGRES else sql, params)
    return cur


# ==========================================
# 🌱 AUTO-SEED DATABASE ON STARTUP
# ==========================================
def seed_database():
    """Create tables and seed initial data if empty."""
    with get_db() as conn:
        cur = conn.cursor()

        if USE_POSTGRES:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    name TEXT PRIMARY KEY,
                    floor INTEGER DEFAULT 1,
                    description TEXT,
                    lat DOUBLE PRECISION DEFAULT 0.0,
                    lng DOUBLE PRECISION DEFAULT 0.0,
                    occupancy_status TEXT DEFAULT 'UNVERIFIED',
                    last_verified TEXT DEFAULT 'Never',
                    image_url TEXT,
                    camera_url TEXT DEFAULT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    id SERIAL PRIMARY KEY,
                    node_from TEXT,
                    node_to TEXT,
                    distance_meters DOUBLE PRECISION,
                    FOREIGN KEY(node_from) REFERENCES nodes(name),
                    FOREIGN KEY(node_to) REFERENCES nodes(name)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS timetable (
                    id SERIAL PRIMARY KEY,
                    course_code TEXT,
                    course_name TEXT,
                    day_of_week TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    venue TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    reg_no TEXT PRIMARY KEY,
                    password TEXT NOT NULL,
                    course TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    semester INTEGER NOT NULL,
                    units TEXT NOT NULL
                )
            """)
        else:
            cur.execute('''CREATE TABLE IF NOT EXISTS nodes (
                name TEXT PRIMARY KEY, floor INTEGER DEFAULT 1, description TEXT,
                lat REAL DEFAULT 0.0, lng REAL DEFAULT 0.0,
                occupancy_status TEXT DEFAULT 'UNVERIFIED',
                last_verified TEXT DEFAULT 'Never', image_url TEXT,
                camera_url TEXT DEFAULT NULL)''')
            cur.execute('''CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_from TEXT, node_to TEXT, distance_meters REAL,
                FOREIGN KEY(node_from) REFERENCES nodes(name),
                FOREIGN KEY(node_to) REFERENCES nodes(name))''')
            cur.execute('''CREATE TABLE IF NOT EXISTS timetable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_code TEXT, course_name TEXT, day_of_week TEXT,
                start_time TEXT, end_time TEXT, venue TEXT)''')
            cur.execute('''CREATE TABLE IF NOT EXISTS students (
                reg_no TEXT PRIMARY KEY, password TEXT NOT NULL,
                course TEXT NOT NULL, year INTEGER NOT NULL,
                semester INTEGER NOT NULL, units TEXT NOT NULL)''')

        conn.commit()

        cur.execute("SELECT COUNT(*) FROM nodes")
        node_count = cur.fetchone()[0] if not USE_POSTGRES else cur.fetchone()[0]

        if node_count == 0:
            nodes = [
                ("Forensic laboratory", 1, "Main laboratory", -1.045600, 37.012300),
                ("Vice chancellors office", 1, "Admin Block", -1.046100, 37.012800),
                ("BS/2", 1, "Hub", -0.092969, 37.989887),
                ("Main Gate Junction", 1, "Entry", -1.045000, 37.011500),
                ("UTC 9", 1, "Lecture", -0.090023, 37.987475),
                ("STB 2", 1, "Lecture", -0.090755, 37.989205),
                ("ED 7", 1, "Lecture", -0.090617, 37.989997),
                ("TC 1", 1, "Lecture", -0.092325, 37.989829),
                ("Bs/1", 1, "Lecture", -0.092576, 37.990462),
                ("Hospitality lab", 1, "Lab", -0.092770, 37.991091),
                ("Forensic laboratory (Old Location)", 1, "Lab", -0.092555, 37.990695),
                ("Bs/3", 1, "Lecture", -0.093857, 37.991478),
            ]
            for n in nodes:
                if USE_POSTGRES:
                    cur.execute("INSERT INTO nodes (name, floor, description, lat, lng, occupancy_status, last_verified) VALUES (%s,%s,%s,%s,%s,'UNVERIFIED','Never') ON CONFLICT (name) DO NOTHING", n)
                else:
                    cur.execute("INSERT OR IGNORE INTO nodes (name, floor, description, lat, lng, occupancy_status, last_verified) VALUES (?,?,?,?,?,'UNVERIFIED','Never')", n)
            print(f"Seeded {len(nodes)} nodes")

        cur.execute("SELECT COUNT(*) FROM edges")
        edge_count = cur.fetchone()[0] if not USE_POSTGRES else cur.fetchone()[0]

        if edge_count == 0:
            edges = [
                ("UTC 9", "UTC 7", 30), ("STB 2", "ED 7", 90), ("ED 7", "Bs/1", 210),
                ("Bs/1", "Forensic laboratory (Old Location)", 45), ("Bs/1", "TC 1", 76),
                ("TC 1", "BS/2", 80), ("BS/2", "Bs/3", 205),
                ("Main Gate Junction", "Forensic laboratory", 96),
                ("Forensic laboratory", "Vice chancellors office", 120),
                ("Main Gate Junction", "Vice chancellors office", 150),
            ]
            for f, t, d in edges:
                if USE_POSTGRES:
                    cur.execute("INSERT INTO edges (node_from, node_to, distance_meters) VALUES (%s,%s,%s)", (f, t, d))
                else:
                    cur.execute("INSERT INTO edges (node_from, node_to, distance_meters) VALUES (?,?,?)", (f, t, d))
            print(f"Seeded {len(edges)} edges")

        conn.commit()

        cur.execute("SELECT COUNT(*) FROM nodes")
        nc = cur.fetchone()[0] if not USE_POSTGRES else cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges")
        ec = cur.fetchone()[0] if not USE_POSTGRES else cur.fetchone()[0]
        print(f"DB ready: {nc} nodes, {ec} edges")

seed_database()


# 3. Pydantic Models for Incoming Data Validation
class VerificationRequest(BaseModel):
    venue: str
    status: str

class NavigationRequest(BaseModel):
    start_node: str
    end_node: str

class StudentRegisterRequest(BaseModel):
    reg_no: str
    password: str
    course: str
    year: int
    semester: int
    units: str

class StudentLoginRequest(BaseModel):
    reg_no: str
    password: str

class AdminLoginRequest(BaseModel):
    admin_password: str

class TimetableEntry(BaseModel):
    course_code: str
    course_name: str
    day_of_week: str
    start_time: str
    end_time: str
    venue: str


@app.get("/health")
def health_check():
    with get_db() as conn:
        cur = execute(conn, "SELECT COUNT(*) FROM nodes")
        node_count = cur.fetchone()[0]
        cur = execute(conn, "SELECT COUNT(*) FROM edges")
        edge_count = cur.fetchone()[0]
        cur = execute(conn, "SELECT COUNT(*) FROM timetable")
        schedule_count = cur.fetchone()[0]
    return {
        "status": "online",
        "database": "postgresql" if USE_POSTGRES else "sqlite",
        "counts": {
            "nodes": node_count,
            "edges": edge_count,
            "schedules": schedule_count
        }
    }


# ==========================================
# 🧭 ENDPOINT 1: THE TIMETABLE ALLOCATION FEED
# ==========================================
@app.get("/rooms/status")
def get_room_status():
    with get_db() as conn:
        current_day = datetime.now().strftime('%A')
        current_time = datetime.now().strftime('%H:%M')

        # Get ALL rooms: from timetable venues AND from named nodes that look like rooms
        timetable_venues = set()
        for row in execute(conn, "SELECT DISTINCT venue FROM timetable WHERE venue IS NOT NULL AND venue != ''").fetchall():
            venue = row['venue'] if not USE_POSTGRES else row[0]
            timetable_venues.add(venue)

        # Also get rooms from nodes that look like venue names
        node_rooms = set()
        campus_nodes_mark = set()
        for row in execute(conn, "SELECT name FROM nodes WHERE name IS NOT NULL AND name != ''").fetchall():
            name = row['name'] if not USE_POSTGRES else row[0]
            if name in timetable_venues:
                node_rooms.add(name)
            elif any(kw in name.lower() for kw in ['hall', 'lab', 'room', 'lecture', 'class', 'office', 'block', 'theatre']):
                node_rooms.add(name)
            else:
                campus_nodes_mark.add(name)

        # Combine all
        all_venue_names = list(timetable_venues | node_rooms)

        rooms_status_feed = []

        for venue_name in all_venue_names:
            if not venue_name:
                continue

            cur = execute(conn, """
                SELECT course_code, course_name, end_time 
                FROM timetable 
                WHERE venue = %s AND day_of_week = %s AND %s BETWEEN start_time AND end_time
                LIMIT 1
            """ if USE_POSTGRES else """
                SELECT course_code, course_name, end_time 
                FROM timetable 
                WHERE venue = ? AND day_of_week = ? AND ? BETWEEN start_time AND end_time
                LIMIT 1
            """, (venue_name, current_day, current_time))
            active_class = cur.fetchone()

            cur = execute(conn, "SELECT occupancy_status, last_verified FROM nodes WHERE name = %s" if USE_POSTGRES else "SELECT occupancy_status, last_verified FROM nodes WHERE name = ?", (venue_name,))
            override = cur.fetchone()

            if override:
                override = dict(override) if not USE_POSTGRES else {"occupancy_status": override[0], "last_verified": override[1]}

            status = "AVAILABLE"
            schedule_text = "📅 No Class Scheduled Right Now"
            time_verified = "⏱️ Synced with System Clock"

            if active_class:
                if USE_POSTGRES:
                    ac = {"course_code": active_class[0], "course_name": active_class[1], "end_time": active_class[2]}
                else:
                    ac = dict(active_class)
                status = "BUSY"
                schedule_text = f"🔴 Ongoing: {ac['course_code']} - {ac['course_name']} (Ends {ac['end_time']})"
            else:
                cur = execute(conn, """
                    SELECT course_code, start_time 
                    FROM timetable 
                    WHERE venue = %s AND day_of_week = %s AND start_time > %s
                    ORDER BY start_time ASC LIMIT 1
                """ if USE_POSTGRES else """
                    SELECT course_code, start_time 
                    FROM timetable 
                    WHERE venue = ? AND day_of_week = ? AND start_time > ?
                    ORDER BY start_time ASC LIMIT 1
                """, (venue_name, current_day, current_time))
                next_class = cur.fetchone()
                if next_class:
                    nc = {"course_code": next_class[0], "start_time": next_class[1]} if USE_POSTGRES else dict(next_class)
                    schedule_text = f"🟢 Inactive: Next class {nc['course_code']} at {nc['start_time']}"

            if override and override.get('occupancy_status', 'UNVERIFIED') != 'UNVERIFIED':
                status = override['occupancy_status']
                schedule_text = f"👥 Room marked as manual {status} via crowd override."
                time_verified = f"Verified at: {override['last_verified']}"

            rooms_status_feed.append({
                "venue": venue_name,
                "status": status,
                "current_schedule": schedule_text,
                "last_verified": time_verified
            })
        return rooms_status_feed


# ==========================================
# 📍 ENDPOINT 2: FETCH GEOGRAPHIC NODES ONLY
# ==========================================
@app.get("/api/geo-nodes")
def get_geo_nodes():
    with get_db() as conn:
        rows = execute(conn, "SELECT name, lat, lng, description, camera_url FROM nodes").fetchall()
        result = []
        for row in rows:
            if USE_POSTGRES:
                result.append({
                    "name": row[0],
                    "lat": row[1],
                    "lng": row[2],
                    "description": row[3],
                    "camera_url": row[4]
                })
            else:
                result.append(dict(row))
        return result


# ==========================================
# 👤 ENDPOINT 3: STUDENT PROFILE REGISTRATION
# ==========================================
@app.post("/students/register")
def register_student(req: StudentRegisterRequest):
    with get_db() as conn:
        try:
            stmt = "INSERT INTO students (reg_no, password, course, year, semester, units) VALUES (%s, %s, %s, %s, %s, %s)" if USE_POSTGRES else "INSERT INTO students (reg_no, password, course, year, semester, units) VALUES (?, ?, ?, ?, ?, ?)"
            execute(conn, stmt, (req.reg_no, req.password, req.course, req.year, req.semester, req.units))
            conn.commit()
            return {"status": "success", "message": "Student registered successfully!"}
        except Exception as e:
            if "duplicate" in str(e).lower() or "unique" in str(e).lower() or "integrity" in str(e).lower():
                raise HTTPException(status_code=400, detail="Registration number already exists.")
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/students/login")
def login_student(req: StudentLoginRequest):
    with get_db() as conn:
        stmt = "SELECT reg_no, course, year, semester, units FROM students WHERE reg_no = %s AND password = %s" if USE_POSTGRES else "SELECT reg_no, course, year, semester, units FROM students WHERE reg_no = ? AND password = ?"
        cur = execute(conn, stmt, (req.reg_no, req.password))
        student = cur.fetchone()
        if not student:
            raise HTTPException(status_code=401, detail="Invalid registration number or password.")
        if USE_POSTGRES:
            return {
                "reg_no": student[0],
                "course": student[1],
                "year": student[2],
                "semester": student[3],
                "units": student[4]
            }
        return dict(student)

@app.post("/admin/login")
def login_admin(req: AdminLoginRequest):
    if req.admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    return {"status": "success", "message": "Admin authenticated."}


# ==========================================
# 📅 ENDPOINT 4: PERSONALIZED SCHEDULE TRACKING
# ==========================================
@app.get("/students/schedule/{reg_no:path}")
def get_student_schedule(reg_no: str):
    with get_db() as conn:
        stmt = "SELECT course, year, semester, units FROM students WHERE reg_no = %s" if USE_POSTGRES else "SELECT course, year, semester, units FROM students WHERE reg_no = ?"
        cur = execute(conn, stmt, (reg_no,))
        student = cur.fetchone()
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")

        if USE_POSTGRES:
            s = {"course": student[0], "year": student[1], "semester": student[2], "units": student[3]}
        else:
            s = dict(student)

        registered_units = [u.strip() for u in s['units'].split(',') if u.strip()]
        current_day = datetime.now().strftime('%A')

        if not registered_units:
            return {
                "day": current_day,
                "student": s,
                "schedule": []
            }

        placeholders = ','.join(['%s' if USE_POSTGRES else '?' for _ in registered_units])
        query = f'''
            SELECT course_code, course_name, start_time, end_time, venue 
            FROM timetable 
            WHERE UPPER(day_of_week) = UPPER(%s) 
              AND (UPPER(course_code) IN ({placeholders}) OR UPPER(venue) IN ({placeholders}))
            ORDER BY start_time ASC
        ''' if USE_POSTGRES else f'''
            SELECT course_code, course_name, start_time, end_time, venue 
            FROM timetable 
            WHERE UPPER(day_of_week) = UPPER(?) 
              AND (UPPER(course_code) IN ({placeholders}) OR UPPER(venue) IN ({placeholders}))
            ORDER BY start_time ASC
        '''
        upper_units = [u.upper() for u in registered_units]
        search_params = (current_day,) + tuple(upper_units) + tuple(upper_units)

        try:
            schedule_rows = execute(conn, query, search_params).fetchall()
        except Exception as e:
            return {"day": current_day, "schedule": [], "error": str(e)}

        schedules = []
        for row in schedule_rows:
            if USE_POSTGRES:
                schedules.append({
                    "course_code": str(row[0]) if row[0] else "UNIT",
                    "course_name": str(row[1]) if row[1] else "Lecture Session",
                    "time": f"{row[2]} - {row[3]}",
                    "venue": str(row[4]) if row[4] else "Unassigned Venue"
                })
            else:
                schedules.append({
                    "course_code": str(row['course_code']) if row['course_code'] else "UNIT",
                    "course_name": str(row['course_name']) if row['course_name'] else "Lecture Session",
                    "time": f"{row['start_time']} - {row['end_time']}",
                    "venue": str(row['venue']) if row['venue'] else "Unassigned Venue"
                })

        return {
            "day": current_day,
            "student": {
                "reg_no": reg_no,
                "course": s['course'],
                "year": s['year'],
                "semester": s['semester'],
                "units": s['units']
            },
            "schedule": schedules
        }


# ==========================================
# 👥 ENDPOINT 5: CROWDSOURCED OVERRIDE REPORTING
# ==========================================
@app.post("/verify")
def verify_room(req: VerificationRequest):
    with get_db() as conn:
        now_str = datetime.now().strftime('%H:%M:%S')

        cur = execute(conn, "SELECT name FROM nodes WHERE name = %s" if USE_POSTGRES else "SELECT name FROM nodes WHERE name = ?", (req.venue,))
        exists = cur.fetchone()

        if not exists:
            stmt = "INSERT INTO nodes (name, floor, description, occupancy_status, last_verified) VALUES (%s, 1, 'Auto-generated via user update', %s, %s)" if USE_POSTGRES else "INSERT INTO nodes (name, floor, description, occupancy_status, last_verified) VALUES (?, 1, 'Auto-generated via user update', ?, ?)"
            execute(conn, stmt, (req.venue, req.status, now_str))
        else:
            stmt = "UPDATE nodes SET occupancy_status = %s, last_verified = %s WHERE name = %s" if USE_POSTGRES else "UPDATE nodes SET occupancy_status = ?, last_verified = ? WHERE name = ?"
            execute(conn, stmt, (req.status, now_str, req.venue))
        conn.commit()
    return {"message": "Telemetry verified successfully"}


# ==========================================
# 🗘 ENDPOINT 6: RESET TELEMETRY OVERRIDES
# ==========================================
@app.post("/rooms/reset")
def reset_rooms():
    with get_db() as conn:
        execute(conn, "UPDATE nodes SET occupancy_status = 'UNVERIFIED', last_verified = 'Never'")
        conn.commit()
        return {"message": "Telemetry cleared successfully"}


# ==========================================
# 🗺️ ENDPOINT 7: DIJKSTRA GEOGRAPHIC NAVIGATION
# ==========================================
@app.post("/navigate")
def navigate(req: NavigationRequest):
    """Calculates shortest walking path and returns coordinates for map drawing."""
    with get_db() as conn:
        rows = execute(conn, "SELECT name, lat, lng FROM nodes").fetchall()
        if USE_POSTGRES:
            nodes_data = {r[0]: {"lat": r[1], "lng": r[2]} for r in rows}
        else:
            nodes_data = {r['name']: {"lat": r['lat'], "lng": r['lng']} for r in rows}
        nodes_list = list(nodes_data.keys())

        edge_rows = execute(conn, "SELECT node_from, node_to, distance_meters FROM edges").fetchall()
        if USE_POSTGRES:
            edges = [{"node_from": r[0], "node_to": r[1], "distance_meters": r[2]} for r in edge_rows]
        else:
            edges = [dict(r) for r in edge_rows]

        if req.start_node not in nodes_data or req.end_node not in nodes_data:
            raise HTTPException(status_code=400, detail="Selected points must exist in mapped data")

        graph = {node: {} for node in nodes_list}
        for edge in edges:
            u, v, w = edge['node_from'], edge['node_to'], edge['distance_meters']
            if u in graph and v in graph:
                graph[u][v] = w
                graph[v][u] = w

        queue = {node: float('inf') for node in nodes_list}
        queue[req.start_node] = 0
        previous = {node: None for node in nodes_list}
        distances = {node: float('inf') for node in nodes_list}
        distances[req.start_node] = 0

        while queue:
            current_node = min(queue, key=queue.get)
            current_dist = queue[current_node]

            if current_dist == float('inf') or current_node == req.end_node:
                break

            del queue[current_node]

            for neighbor, weight in graph[current_node].items():
                alt_path = distances[current_node] + weight
                if alt_path < distances[neighbor]:
                    distances[neighbor] = alt_path
                    previous[neighbor] = current_node
                    if neighbor in queue:
                        queue[neighbor] = alt_path

    if distances[req.end_node] == float('inf'):
        raise HTTPException(status_code=404, detail="No viable walking paths found between locations")

    path = []
    curr = req.end_node
    while curr is not None:
        path.append(curr)
        curr = previous[curr]
    path.reverse()

    # Generate coordinates for the path
    coordinates = []
    for node_name in path:
        node = nodes_data.get(node_name)
        if node and node['lat'] and node['lng']:
            coordinates.append([node['lat'], node['lng']])

    # Also generate weighted coordinates for a smoother line
    detailed_coords = []
    for i, node_name in enumerate(path):
        node = nodes_data.get(node_name)
        if node and node['lat'] and node['lng']:
            detailed_coords.append([node['lat'], node['lng']])
            if i < len(path) - 1:
                next_node = nodes_data.get(path[i+1])
                if next_node and next_node['lat'] and next_node['lng']:
                    mid_lat = (node['lat'] + next_node['lat']) / 2
                    mid_lng = (node['lng'] + next_node['lng']) / 2
                    detailed_coords.append([mid_lat, mid_lng])

    return {
        "total_distance_meters": round(distances[req.end_node], 1),
        "routing_path": path,
        "coordinates": detailed_coords if len(detailed_coords) >= 2 else coordinates
    }


# ============================================================
# 📋 ENDPOINT 8: ADMIN TIMETABLE MANAGEMENT
# ============================================================

# --- 8a: Upload PDF timetable ---
@app.post("/admin/timetable/upload-pdf")
async def upload_timetable_pdf(admin_password: str = Form(...), file: UploadFile = File(...)):
    """Upload any .pdf timetable."""
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_path = os.path.join(UPLOAD_DIR, "uploaded_timetable.pdf")
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        import pdfplumber
    except ImportError:
        raise HTTPException(status_code=500, detail="pdfplumber library is not installed.")

    parsed_classes = []
    VALID_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    TIME_SLOTS_BY_ROW = [
        "", "08:00-10:00", "10:00-12:00", "12:00-14:00", "14:00-16:00",
        "16:00-18:00", "18:00-20:00", "08:00-10:00", "10:00-12:00", "12:00-14:00",
    ]

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                table = page.extract_table()
                if not table or len(table) < 2:
                    continue

                num_cols = len(table[0]) if table[0] else 0
                print(f"Page {page_num}: {len(table)} rows x {num_cols} columns")

                header = table[0]
                day_boundaries = {}
                current_day = None

                for col_idx, cell in enumerate(header):
                    cell_text = cell.strip() if cell else ""
                    cell_lower = cell_text.lower()

                    if cell_lower in VALID_DAYS:
                        current_day = cell_text.capitalize()
                        if current_day not in day_boundaries:
                            day_boundaries[current_day] = []
                        day_boundaries[current_day].append(col_idx)
                    elif current_day is not None and cell_text:
                        day_boundaries[current_day].append(col_idx)

                print(f"   Detected days: {list(day_boundaries.keys())}")

                if not day_boundaries:
                    print(f"   Skipping page {page_num} (no day headers)")
                    continue

                rows_this_page = 0

                for row_idx in range(1, len(table)):
                    row = table[row_idx]
                    if not row:
                        continue

                    time_label = TIME_SLOTS_BY_ROW[row_idx] if row_idx < len(TIME_SLOTS_BY_ROW) else f"{8 + (row_idx-1)*2:02d}:00-{10 + (row_idx-1)*2:02d}:00"

                    has_any_data = False
                    for day_name, col_indices in day_boundaries.items():
                        for ci in col_indices:
                            if ci < len(row) and row[ci] and row[ci].strip():
                                has_any_data = True
                                break
                        if has_any_data:
                            break

                    if not has_any_data:
                        continue

                    for day_name, col_indices in day_boundaries.items():
                        day_cells_text = []
                        for ci in col_indices:
                            if ci < len(row) and row[ci] and row[ci].strip():
                                day_cells_text.append(row[ci].strip())

                        if not day_cells_text:
                            continue

                        items = []
                        for ct in day_cells_text:
                            parts = ct.replace("\n", " ").split()
                            items.extend(parts)

                        if not items:
                            continue

                        course_code = ""
                        venue = ""

                        venue_keywords = ["hall", "lab", "room", "stb", "tc", "ed", "bs", "utc", "phil", "econ", "bs/", "main"]

                        venue_start = -1
                        for i, item in enumerate(items):
                            item_lower = item.lower()
                            if item_lower in ["stb", "tc", "ed", "bs", "utc", "phil", "econ", "lab", "hall", "room", "main"]:
                                venue_start = i
                                break
                            if any(kw in item_lower for kw in venue_keywords):
                                venue_start = i
                                break

                        if venue_start >= 0:
                            code_parts = items[:venue_start]
                            venue_parts = items[venue_start:]
                            course_code = " ".join(code_parts)
                            venue = " ".join(venue_parts)
                        else:
                            if len(items) >= 3:
                                last = items[-1]
                                second_last = items[-2] if len(items) >= 2 else ""
                                if any(kw in last.lower() for kw in ["tc", "stb", "bs", "utc", "ed"]):
                                    venue = last
                                    course_code = " ".join(items[:-1])
                                elif any(kw in second_last.lower() for kw in ["tc", "stb", "bs", "utc", "ed"]):
                                    venue = second_last + " " + last
                                    course_code = " ".join(items[:-2])
                                else:
                                    course_code = " ".join(items)
                                    venue = course_code
                            elif len(items) == 2:
                                course_code = items[0]
                                venue = items[1]
                            else:
                                course_code = items[0]
                                venue = items[0]

                        if not course_code:
                            continue
                        if not venue:
                            venue = course_code

                        start_time = "08:00"
                        end_time = "10:00"
                        if "-" in time_label:
                            parts = time_label.split("-")
                            if len(parts) >= 2:
                                st, et = parts[0].strip(), parts[-1].strip()
                                if ":" in st and ":" in et:
                                    if len(st.split(":")[0]) == 1: st = "0" + st
                                    if len(et.split(":")[0]) == 1: et = "0" + et
                                    start_time, end_time = st, et

                        parsed_classes.append({
                            "course_code": course_code,
                            "course_name": course_code,
                            "day_of_week": day_name,
                            "start_time": start_time,
                            "end_time": end_time,
                            "venue": venue
                        })
                        rows_this_page += 1

                print(f"   Page {page_num}: +{rows_this_page} entries (total: {len(parsed_classes)})")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {str(e)}")

    if not parsed_classes:
        raise HTTPException(status_code=400, detail="No class data could be extracted.")

    # Replace all timetable data
    with get_db() as conn:
        execute(conn, "DELETE FROM timetable")
        for entry in parsed_classes:
            stmt = "INSERT INTO timetable (course_code, course_name, day_of_week, start_time, end_time, venue) VALUES (%s, %s, %s, %s, %s, %s)" if USE_POSTGRES else "INSERT INTO timetable (course_code, course_name, day_of_week, start_time, end_time, venue) VALUES (?, ?, ?, ?, ?, ?)"
            execute(conn, stmt, (entry["course_code"], entry["course_name"], entry["day_of_week"], entry["start_time"], entry["end_time"], entry["venue"]))
        conn.commit()

    return {
        "status": "success",
        "message": f"Timetable updated successfully!",
        "classes_imported": len(parsed_classes)
    }


# --- 8b: Get all timetable entries ---
@app.get("/admin/timetable/all")
def get_all_timetable(admin_password: str = Query(...)):
    """Admin-only: Get all timetable entries."""
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")

    with get_db() as conn:
        rows = execute(conn, """
            SELECT id, course_code, course_name, day_of_week, start_time, end_time, venue
            FROM timetable ORDER BY day_of_week, start_time
        """).fetchall()
        if USE_POSTGRES:
            return [{"id": r[0], "course_code": r[1], "course_name": r[2], "day_of_week": r[3], "start_time": r[4], "end_time": r[5], "venue": r[6]} for r in rows]
        return [dict(row) for row in rows]


# --- 8c: Add a timetable entry manually ---
@app.post("/admin/timetable/add")
def add_timetable_entry(admin_password: str = Query(...), entry: TimetableEntry = None):
    """Admin-only: Add a single timetable entry."""
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")

    with get_db() as conn:
        stmt = "INSERT INTO timetable (course_code, course_name, day_of_week, start_time, end_time, venue) VALUES (%s, %s, %s, %s, %s, %s)" if USE_POSTGRES else "INSERT INTO timetable (course_code, course_name, day_of_week, start_time, end_time, venue) VALUES (?, ?, ?, ?, ?, ?)"
        cur = execute(conn, stmt, (entry.course_code, entry.course_name, entry.day_of_week, entry.start_time, entry.end_time, entry.venue))
        conn.commit()
        if USE_POSTGRES:
            # Get the last inserted id
            cur = execute(conn, "SELECT LASTVAL()")
            new_id = cur.fetchone()[0]
        else:
            new_id = execute(conn, "SELECT last_insert_rowid()").fetchone()[0]

    return {"status": "success", "message": "Entry added successfully!", "id": new_id}


# --- 8d: Update a timetable entry ---
@app.put("/admin/timetable/update/{entry_id}")
def update_timetable_entry(entry_id: int, admin_password: str = Query(...), entry: TimetableEntry = None):
    """Admin-only: Update a timetable entry by ID."""
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")

    with get_db() as conn:
        cur = execute(conn, "SELECT id FROM timetable WHERE id = %s" if USE_POSTGRES else "SELECT id FROM timetable WHERE id = ?", (entry_id,))
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Entry not found.")

        stmt = "UPDATE timetable SET course_code=%s, course_name=%s, day_of_week=%s, start_time=%s, end_time=%s, venue=%s WHERE id=%s" if USE_POSTGRES else "UPDATE timetable SET course_code=?, course_name=?, day_of_week=?, start_time=?, end_time=?, venue=? WHERE id=?"
        execute(conn, stmt, (entry.course_code, entry.course_name, entry.day_of_week, entry.start_time, entry.end_time, entry.venue, entry_id))
        conn.commit()

    return {"status": "success", "message": "Entry updated successfully!"}


# --- 8e: Delete a timetable entry ---
@app.delete("/admin/timetable/delete/{entry_id}")
def delete_timetable_entry(entry_id: int, admin_password: str = Query(...)):
    """Admin-only: Delete a timetable entry by ID."""
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")

    with get_db() as conn:
        cur = execute(conn, "SELECT id FROM timetable WHERE id = %s" if USE_POSTGRES else "SELECT id FROM timetable WHERE id = ?", (entry_id,))
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Entry not found.")

        execute(conn, "DELETE FROM timetable WHERE id = %s" if USE_POSTGRES else "DELETE FROM timetable WHERE id = ?", (entry_id,))
        conn.commit()

    return {"status": "success", "message": "Entry deleted successfully!"}


# --- 8f: Get all unique venues ---
@app.get("/admin/timetable/venues")
def get_all_venues(admin_password: str = Query(...)):
    """Admin-only: Get list of unique venues."""
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")

    with get_db() as conn:
        venues = execute(conn, "SELECT DISTINCT venue FROM timetable ORDER BY venue").fetchall()
        if USE_POSTGRES:
            return [v[0] for v in venues if v[0]]
        return [v["venue"] for v in venues if v["venue"]]


# --- 8g: Clear entire timetable ---
@app.delete("/admin/timetable/clear")
def clear_timetable(admin_password: str = Query(...)):
    """Admin-only: Clear all timetable entries."""
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")

    with get_db() as conn:
        execute(conn, "DELETE FROM timetable")
        conn.commit()

    return {"status": "success", "message": "All timetable entries cleared!"}


# ============================================================
# 🎓 ENDPOINT 9: SMART UNIT SELECTION FOR STUDENT REGISTRATION
# ============================================================
class SetCameraRequest(BaseModel):
    camera_url: str = ""

class NodeAddRequest(BaseModel):
    name: str
    lat: float
    lng: float
    floor: int = 1
    description: str = ""


@app.get("/students/available-units")
def get_available_units(course: str = Query(""), year: int = Query(0), semester: int = Query(0)):
    """Returns distinct course codes filtered by course name, year, semester."""
    with get_db() as conn:
        rows = execute(conn, "SELECT DISTINCT course_code, course_name, day_of_week, start_time, end_time, venue FROM timetable ORDER BY course_code").fetchall()
        seen = {}
        for row in rows:
            if USE_POSTGRES:
                code = str(row[0]) if row[0] else ""
                name = str(row[1]) if row[1] else ""
                venue = str(row[4]) if row[4] else ""
                day = str(row[2]) if row[2] else ""
            else:
                code = str(row['course_code']) if row['course_code'] else ""
                name = str(row['course_name']) if row['course_name'] else ""
                venue = str(row['venue']) if row['venue'] else ""
                day = str(row['day_of_week']) if row['day_of_week'] else ""
            if not code:
                continue
            if year > 0:
                nums = [int(s) for s in code.split() if s.isdigit()]
                if nums:
                    first_digit = int(str(nums[0])[0])
                    if first_digit != year:
                        if year not in [int(d) for d in str(nums[0])]:
                            continue
            if course:
                course_lower = course.lower()
                course_keywords = course_lower.split()
                match_found = False
                for kw in course_keywords:
                    if len(kw) < 2:
                        continue
                    if kw in name.lower() or kw in venue.lower() or kw in code.lower():
                        match_found = True
                        break
                if not match_found:
                    words = course_lower.split()
                    acronyms = []
                    for w in words:
                        if len(w) >= 2 and w not in ['of', 'in', 'and', 'the', 'for']:
                            acronyms.append(w[:3].upper())
                    for ac in acronyms:
                        if ac and (ac in code.upper() or ac in venue.upper()):
                            match_found = True
                            break
                if not match_found:
                    continue
            if code not in seen:
                seen[code] = {"code": code, "name": name if name and name != code else "", "venue": venue, "day": day}
        unique = list(seen.values())
        if course:
            course_lower = course.lower()
            def sort_key(item):
                score = 0
                if course_lower in item['venue'].lower(): score += 3
                if course_lower in item['name'].lower(): score += 2
                if course_lower in item['code'].lower(): score += 1
                return -score
            unique.sort(key=sort_key)
        return {"units": unique, "total": len(unique)}


# ============================================================
# 📌 ENDPOINT 10: ADMIN NODE MANAGEMENT
# ============================================================
@app.get("/admin/nodes/all")
def get_all_nodes(admin_password: str = Query(...)):
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    with get_db() as conn:
        rows = execute(conn, "SELECT name, lat, lng, floor, description, occupancy_status, camera_url FROM nodes ORDER BY name").fetchall()
        if USE_POSTGRES:
            return [{"name": r[0], "lat": r[1], "lng": r[2], "floor": r[3], "description": r[4], "occupancy_status": r[5], "camera_url": r[6]} for r in rows]
        return [dict(row) for row in rows]

@app.post("/admin/nodes/add")
def add_node(admin_password: str = Query(...), node: NodeAddRequest = None):
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    if not node.name or not node.name.strip():
        raise HTTPException(status_code=400, detail="Node name is required.")
    with get_db() as conn:
        cur = execute(conn, "SELECT name FROM nodes WHERE name = %s" if USE_POSTGRES else "SELECT name FROM nodes WHERE name = ?", (node.name.strip(),))
        existing = cur.fetchone()
        if existing:
            raise HTTPException(status_code=400, detail=f"Node '{node.name}' already exists.")
        stmt = "INSERT INTO nodes (name, floor, description, lat, lng, occupancy_status, last_verified) VALUES (%s, %s, %s, %s, %s, 'UNVERIFIED', 'Never')" if USE_POSTGRES else "INSERT INTO nodes (name, floor, description, lat, lng, occupancy_status, last_verified) VALUES (?, ?, ?, ?, ?, 'UNVERIFIED', 'Never')"
        execute(conn, stmt, (node.name.strip(), node.floor, node.description, node.lat, node.lng))
        conn.commit()
    return {"status": "success", "message": f"Node '{node.name}' added!"}

@app.delete("/admin/nodes/delete/{node_name}")
def delete_node(node_name: str, admin_password: str = Query(...)):
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    with get_db() as conn:
        cur = execute(conn, "SELECT name FROM nodes WHERE name = %s" if USE_POSTGRES else "SELECT name FROM nodes WHERE name = ?", (node_name,))
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found.")
        execute(conn, "DELETE FROM edges WHERE node_from = %s OR node_to = %s" if USE_POSTGRES else "DELETE FROM edges WHERE node_from = ? OR node_to = ?", (node_name, node_name))
        execute(conn, "DELETE FROM nodes WHERE name = %s" if USE_POSTGRES else "DELETE FROM nodes WHERE name = ?", (node_name,))
        conn.commit()
    return {"status": "success", "message": f"Node '{node_name}' deleted!"}

@app.put("/admin/nodes/update/{node_name}")
def update_node(node_name: str, admin_password: str = Query(...), node: NodeAddRequest = None):
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    with get_db() as conn:
        cur = execute(conn, "SELECT name FROM nodes WHERE name = %s" if USE_POSTGRES else "SELECT name FROM nodes WHERE name = ?", (node_name,))
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found.")
        stmt = "UPDATE nodes SET lat=%s, lng=%s, floor=%s, description=%s WHERE name=%s" if USE_POSTGRES else "UPDATE nodes SET lat=?, lng=?, floor=?, description=? WHERE name=?"
        execute(conn, stmt, (node.lat, node.lng, node.floor, node.description, node_name))
        conn.commit()
    return {"status": "success", "message": f"Node '{node_name}' updated!"}


# ============================================================
# 📹 ENDPOINT 11: CCTV CAMERA MANAGEMENT
# ============================================================
@app.post("/admin/nodes/camera/{node_name}")
def set_node_camera(node_name: str, admin_password: str = Query(...), req: SetCameraRequest = None):
    """Admin-only: Set/update the CCTV camera URL for a campus node."""
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    with get_db() as conn:
        cur = execute(conn, "SELECT name FROM nodes WHERE name = %s" if USE_POSTGRES else "SELECT name FROM nodes WHERE name = ?", (node_name,))
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found.")
        stmt = "UPDATE nodes SET camera_url = %s WHERE name = %s" if USE_POSTGRES else "UPDATE nodes SET camera_url = ? WHERE name = ?"
        execute(conn, stmt, (req.camera_url, node_name))
        conn.commit()
    return {"status": "success", "message": f"Camera URL for '{node_name}' updated!", "camera_url": req.camera_url}