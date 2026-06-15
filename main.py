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
import sqlite3

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Campus@123')

# 1. Initialize the FastAPI application instance
app = FastAPI()

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

@contextmanager
def get_db():
    conn = sqlite3.connect('campus_navigation.db')
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

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
        node_count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        schedule_count = conn.execute("SELECT COUNT(*) FROM timetable").fetchone()[0]
    return {
        "status": "online",
        "database": "connected",
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
        timetable_venues = conn.execute("SELECT DISTINCT venue FROM timetable").fetchall()
        
        current_day = datetime.now().strftime('%A')
        current_time = datetime.now().strftime('%H:%M')
        
        rooms_status_feed = []
        
        for row in timetable_venues:
            venue_name = row['venue']
            if not venue_name:
                continue
                
            active_class = conn.execute('''
                SELECT course_code, course_name, end_time 
                FROM timetable 
                WHERE venue = ? AND day_of_week = ? AND ? BETWEEN start_time AND end_time
                LIMIT 1
            ''', (venue_name, current_day, current_time)).fetchone()
            
            override = conn.execute(
                "SELECT occupancy_status, last_verified FROM nodes WHERE name = ?", 
                (venue_name,)
            ).fetchone()
            
            status = "AVAILABLE"
            schedule_text = "📅 No Class Scheduled Right Now"
            time_verified = "⏱️ Synced with System Clock"
            
            if active_class:
                status = "BUSY"
                schedule_text = f"🔴 Ongoing: {active_class['course_code']} - {active_class['course_name']} (Ends {active_class['end_time']})"
            else:
                next_class = conn.execute('''
                    SELECT course_code, start_time 
                    FROM timetable 
                    WHERE venue = ? AND day_of_week = ? AND start_time > ?
                    ORDER BY start_time ASC LIMIT 1
                ''', (venue_name, current_day, current_time)).fetchone()
                if next_class:
                    schedule_text = f"🟢 Inactive: Next class {next_class['course_code']} at {next_class['start_time']}"
            
            if override and override['occupancy_status'] != 'UNVERIFIED':
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
        rows = conn.execute("SELECT name, lat, lng, description FROM nodes").fetchall()
        return [
            {
                "name": row['name'],
                "lat": row['lat'],
                "lng": row['lng'],
                "description": row['description']
            } for row in rows
        ]


# ==========================================
# 👤 ENDPOINT 3: STUDENT PROFILE REGISTRATION
# ==========================================
@app.post("/students/register")
def register_student(req: StudentRegisterRequest):
    with get_db() as conn:
        try:
            conn.execute('''
                INSERT INTO students (reg_no, password, course, year, semester, units)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (req.reg_no, req.password, req.course, req.year, req.semester, req.units))
            conn.commit()
            return {"status": "success", "message": "Student registered successfully!"}
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Registration number already exists.")

@app.post("/students/login")
def login_student(req: StudentLoginRequest):
    with get_db() as conn:
        student = conn.execute(
            "SELECT reg_no, course, year, semester, units FROM students WHERE reg_no = ? AND password = ?",
            (req.reg_no, req.password)
        ).fetchone()
        if not student:
            raise HTTPException(status_code=401, detail="Invalid registration number or password.")
        return {
            "reg_no": student['reg_no'],
            "course": student['course'],
            "year": student['year'],
            "semester": student['semester'],
            "units": student['units']
        }

@app.post("/admin/login")
def login_admin(req: AdminLoginRequest):
    if req.admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    return {"status": "success", "message": "Admin authenticated."}

# ==========================================
# 📅 ENDPOINT 4: PERSONALIZED SCHEDULE TRACKING
# ==========================================
@app.get("/students/schedule/{reg_no}")
def get_student_schedule(reg_no: str):
    with get_db() as conn:
        student = conn.execute("SELECT course, year, semester, units FROM students WHERE reg_no = ?", (reg_no,)).fetchone()
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")
        
        registered_units = [u.strip() for u in student['units'].split(',') if u.strip()]
        current_day = datetime.now().strftime('%A')
        
        if not registered_units:
            return {
                "day": current_day,
                "student": dict(student),
                "schedule": []
            }
        
        placeholders = ','.join('?' for _ in registered_units)
        query = f'''
            SELECT course_code, course_name, start_time, end_time, venue 
            FROM timetable 
            WHERE UPPER(day_of_week) = UPPER(?) 
              AND (UPPER(course_code) IN ({placeholders}) OR UPPER(venue) IN ({placeholders}))
            ORDER BY start_time ASC
        '''
        upper_units = [u.upper() for u in registered_units]
        search_params = [current_day] + upper_units + upper_units
        
        try:
            schedule_rows = conn.execute(query, search_params).fetchall()
        except Exception as e:
            return {"day": current_day, "schedule": [], "error": str(e)}
        
        schedules = []
        for row in schedule_rows:
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
                "course": student['course'],
                "year": student['year'],
                "semester": student['semester'],
                "units": student['units']
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
        exists = conn.execute("SELECT name FROM nodes WHERE name = ?", (req.venue,)).fetchone()
        
        if not exists:
            conn.execute('''
                INSERT INTO nodes (name, floor, description, occupancy_status, last_verified) 
                VALUES (?, 1, 'Auto-generated via user update', ?, ?)
            ''', (req.venue, req.status, now_str))
        else:
            conn.execute('''
                UPDATE nodes 
                SET occupancy_status = ?, last_verified = ? 
                WHERE name = ?
            ''', (req.status, now_str, req.venue))
        conn.commit()
    return {"message": "Telemetry verified successfully"}


# ==========================================
# 🗘 ENDPOINT 6: RESET TELEMETRY OVERRIDES
# ==========================================
@app.post("/rooms/reset")
def reset_rooms():
    with get_db() as conn:
        conn.execute("UPDATE nodes SET occupancy_status = 'UNVERIFIED', last_verified = 'Never'")
        conn.commit()
        return {"message": "Telemetry cleared successfully"}


# ==========================================
# 🗺️ ENDPOINT 7: DIJKSTRA GEOGRAPHIC NAVIGATION
# ==========================================
@app.post("/navigate")
def navigate(req: NavigationRequest):
    """Calculates shortest walking path between two named campus nodes."""
    with get_db() as conn:
        nodes = [r['name'] for r in conn.execute("SELECT name FROM nodes").fetchall()]
        edges = conn.execute("SELECT node_from, node_to, distance_meters FROM edges").fetchall()
        
        if req.start_node not in nodes or req.end_node not in nodes:
            raise HTTPException(status_code=400, detail="Selected points must exist in mapped data")
            
        graph = {node: {} for node in nodes}
        for edge in edges:
            u, v, w = edge['node_from'], edge['node_to'], edge['distance_meters']
            if u in graph and v in graph:
                graph[u][v] = w
                graph[v][u] = w 
                
        queue = {node: float('inf') for node in nodes}
        queue[req.start_node] = 0
        previous = {node: None for node in nodes}
        distances = {node: float('inf') for node in nodes}
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
    
    return {
        "total_distance_meters": round(distances[req.end_node], 1),
        "routing_path": path
    }


# ============================================================
# 📋 ENDPOINT 8: ADMIN TIMETABLE MANAGEMENT (Upload / View / Edit / Delete)
# ============================================================

# --- 8a: Upload PDF timetable ---
@app.post("/admin/timetable/upload-pdf")
async def upload_timetable_pdf(admin_password: str = Form(...), file: UploadFile = File(...)):
    """Admin-only: Upload a PDF timetable, parse it, replace all timetable data."""
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    
    # Save uploaded PDF
    pdf_path = os.path.join(UPLOAD_DIR, "uploaded_timetable.pdf")
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Parse PDF using pdfplumber
    try:
        import pdfplumber
    except ImportError:
        raise HTTPException(status_code=500, detail="pdfplumber library is not installed.")
    
    parsed_classes = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if not table:
                    continue
                
                # Try to detect header row - skip if it's a header
                for row_idx, row in enumerate(table):
                    if not row or len(row) < 5:
                        continue
                    
                    # Skip header rows (containing words like "Day", "Time", "Course")
                    first_cell = str(row[0]).strip().lower() if row[0] else ""
                    if first_cell in ("day", "time", "day/time", "code", "course code", "subject"):
                        continue
                    
                    try:
                        day = str(row[0]).strip() if row[0] else "Monday"
                        time_slot = str(row[1]).strip() if row[1] else "08:00-11:00"
                        course_code = str(row[2]).strip() if row[2] else "UNKNOWN"
                        course_name = str(row[3]).strip() if row[3] else "General Lecture"
                        venue = str(row[4]).strip() if row[4] else "Main Hall"

                        # Handle various time formats: "08:00-11:00", "08:00 - 11:00", "8:00-11:00"
                        time_slot_clean = time_slot.replace(" ", "")
                        if "-" in time_slot_clean and time_slot_clean.count(":") >= 2:
                            parts = time_slot_clean.split("-")
                            start_time = parts[0].strip()
                            end_time = parts[-1].strip()  # Use last part in case of extra dashes
                            # Pad single-digit hours: "8:00" -> "08:00"
                            if start_time.count(":") == 1 and len(start_time.split(":")[0]) == 1:
                                start_time = "0" + start_time
                            if end_time.count(":") == 1 and len(end_time.split(":")[0]) == 1:
                                end_time = "0" + end_time
                        else:
                            start_time, end_time = "08:00", "11:00"
                        
                        parsed_classes.append({
                            "course_code": course_code,
                            "course_name": course_name,
                            "day_of_week": day,
                            "start_time": start_time,
                            "end_time": end_time,
                            "venue": venue
                        })
                    except Exception:
                        continue  # Skip unparseable rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {str(e)}")
    
    if not parsed_classes:
        raise HTTPException(status_code=400, detail="No class data could be extracted from the PDF. Check the table structure.")
    
    # Replace all timetable data
    with get_db() as conn:
        conn.execute("DELETE FROM timetable")
        for entry in parsed_classes:
            conn.execute('''
                INSERT INTO timetable (course_code, course_name, day_of_week, start_time, end_time, venue)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (entry["course_code"], entry["course_name"], entry["day_of_week"],
                  entry["start_time"], entry["end_time"], entry["venue"]))
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
        rows = conn.execute('''
            SELECT id, course_code, course_name, day_of_week, start_time, end_time, venue
            FROM timetable ORDER BY day_of_week, start_time
        ''').fetchall()
        return [dict(row) for row in rows]


# --- 8c: Add a timetable entry manually ---
@app.post("/admin/timetable/add")
def add_timetable_entry(admin_password: str = Query(...), entry: TimetableEntry = None):
    """Admin-only: Add a single timetable entry."""
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    
    with get_db() as conn:
        conn.execute('''
            INSERT INTO timetable (course_code, course_name, day_of_week, start_time, end_time, venue)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (entry.course_code, entry.course_name, entry.day_of_week,
              entry.start_time, entry.end_time, entry.venue))
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    
    return {"status": "success", "message": "Entry added successfully!", "id": new_id}


# --- 8d: Update a timetable entry ---
@app.put("/admin/timetable/update/{entry_id}")
def update_timetable_entry(entry_id: int, admin_password: str = Query(...), entry: TimetableEntry = None):
    """Admin-only: Update a timetable entry by ID."""
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM timetable WHERE id = ?", (entry_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Entry not found.")
        
        conn.execute('''
            UPDATE timetable SET course_code=?, course_name=?, day_of_week=?, start_time=?, end_time=?, venue=?
            WHERE id=?
        ''', (entry.course_code, entry.course_name, entry.day_of_week,
              entry.start_time, entry.end_time, entry.venue, entry_id))
        conn.commit()
    
    return {"status": "success", "message": "Entry updated successfully!"}


# --- 8e: Delete a timetable entry ---
@app.delete("/admin/timetable/delete/{entry_id}")
def delete_timetable_entry(entry_id: int, admin_password: str = Query(...)):
    """Admin-only: Delete a timetable entry by ID."""
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM timetable WHERE id = ?", (entry_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Entry not found.")
        
        conn.execute("DELETE FROM timetable WHERE id = ?", (entry_id,))
        conn.commit()
    
    return {"status": "success", "message": "Entry deleted successfully!"}


# --- 8f: Get all unique venues (for reference) ---
@app.get("/admin/timetable/venues")
def get_all_venues(admin_password: str = Query(...)):
    """Admin-only: Get list of unique venues."""
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    
    with get_db() as conn:
        venues = conn.execute("SELECT DISTINCT venue FROM timetable ORDER BY venue").fetchall()
        return [v["venue"] for v in venues if v["venue"]]


# --- 8g: Clear entire timetable ---
@app.delete("/admin/timetable/clear")
def clear_timetable(admin_password: str = Query(...)):
    """Admin-only: Clear all timetable entries."""
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    
    with get_db() as conn:
        conn.execute("DELETE FROM timetable")
        conn.commit()
    
    return {"status": "success", "message": "All timetable entries cleared!"}