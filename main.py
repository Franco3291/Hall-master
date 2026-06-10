import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
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
    units: str # Expecting comma-separated string like "CCS 311,BCS 304"

class StudentLoginRequest(BaseModel):
    reg_no: str
    password: str

class AdminLoginRequest(BaseModel):
    admin_password: str


# ==========================================
# 🧭 ENDPOINT 1: THE TIMETABLE ALLOCATION FEED
# ==========================================
@app.get("/rooms/status")
def get_room_status():
    conn = sqlite3.connect('campus_navigation.db')
    conn.row_factory = sqlite3.Row
    
    # Fetch EVERY unique venue directly from your parsed PDF timetable data
    timetable_venues = conn.execute("SELECT DISTINCT venue FROM timetable").fetchall()
    
    current_day = datetime.now().strftime('%A')
    current_time = datetime.now().strftime('%H:%M')
    
    rooms_status_feed = []
    
    for row in timetable_venues:
        venue_name = row['venue']
        if not venue_name:
            continue
            
        # Check if there is an active class right now for this venue
        active_class = conn.execute('''
            SELECT course_code, course_name, end_time 
            FROM timetable 
            WHERE venue = ? AND day_of_week = ? AND ? BETWEEN start_time AND end_time
            LIMIT 1
        ''', (venue_name, current_day, current_time)).fetchone()
        
        # Check for crowdsourced override flags in the nodes tracking system
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
            # Look up next upcoming class for this room today
            next_class = conn.execute('''
                SELECT course_code, start_time 
                FROM timetable 
                WHERE venue = ? AND day_of_week = ? AND start_time > ?
                ORDER BY start_time ASC LIMIT 1
            ''', (venue_name, current_day, current_time)).fetchone()
            if next_class:
                schedule_text = f"🟢 Inactive: Next class {next_class['course_code']} at {next_class['start_time']}"
        
        # Apply crowdsourced manual reporting changes if they exist
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
        
    conn.close()
    return rooms_status_feed


# ==========================================
# 📍 ENDPOINT 2: FETCH GEOGRAPHIC NODES ONLY
# ==========================================
@app.get("/api/geo-nodes")
def get_geo_nodes():
    conn = sqlite3.connect('campus_navigation.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    rows = cursor.execute("SELECT name, lat, lng, description FROM nodes").fetchall()
    conn.close()
    
    nodes_list = []
    for row in rows:
        nodes_list.append({
            "name": row['name'],
            "lat": row['lat'],
            "lng": row['lng'],
            "description": row['description']
        })
    return nodes_list


# ==========================================
# 👤 ENDPOINT 3: STUDENT PROFILE REGISTRATION
# ==========================================
@app.post("/students/register")
def register_student(req: StudentRegisterRequest):
    conn = sqlite3.connect('campus_navigation.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO students (reg_no, password, course, year, semester, units)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (req.reg_no, req.password, req.course, req.year, req.semester, req.units))
        conn.commit()
        return {"status": "success", "message": "Student registered successfully!"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Registration number already exists.")
    finally:
        conn.close()

@app.post("/students/login")
def login_student(req: StudentLoginRequest):
    conn = sqlite3.connect('campus_navigation.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    student = cursor.execute(
        "SELECT reg_no, course, year, semester, units FROM students WHERE reg_no = ? AND password = ?",
        (req.reg_no, req.password)
    ).fetchone()
    conn.close()
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
# 📅 ENDPOINT 4: PERSONALIZED SCHEDULE TRACKING (FIXED)
# ==========================================
@app.get("/students/schedule/{reg_no}")
def get_student_schedule(reg_no: str):
    conn = sqlite3.connect('campus_navigation.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    student = cursor.execute("SELECT course, year, semester, units FROM students WHERE reg_no = ?", (reg_no,)).fetchone()
    if not student:
        conn.close()
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    registered_units = [u.strip() for u in student['units'].split(',') if u.strip()]
    current_day = datetime.now().strftime('%A')
    
    if not registered_units:
        conn.close()
        return {
            "day": current_day,
            "student": {
                "reg_no": reg_no,
                "course": student['course'],
                "year": student['year'],
                "semester": student['semester'],
                "units": student['units']
            },
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
    # We use the registered units list twice in the query (course_code OR venue),
    # so duplicate the params to match the two placeholder groups.
    upper_units = [u.upper() for u in registered_units]
    search_params = [current_day] + upper_units + upper_units
    
    try:
        schedule_rows = cursor.execute(query, search_params).fetchall()
    except Exception as e:
        conn.close()
        return {"day": current_day, "schedule": [], "error": str(e)}
    conn.close()
    
    schedules = []
    for row in schedule_rows:
        code = row['course_code'] if ('course_code' in row.keys() and row['course_code']) else "UNIT"
        name = row['course_name'] if ('course_name' in row.keys() and row['course_name']) else "Lecture Session"
        start = row['start_time'] if ('start_time' in row.keys() and row['start_time']) else "00:00"
        end = row['end_time'] if ('end_time' in row.keys() and row['end_time']) else "00:00"
        rm_venue = row['venue'] if ('venue' in row.keys() and row['venue']) else "Unassigned Venue"
        
        schedules.append({
            "course_code": str(code),
            "course_name": str(name),
            "time": f"{start} - {end}",
            "venue": str(rm_venue)
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
    conn = sqlite3.connect('campus_navigation.db')
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%H:%M:%S')
    
    cursor.execute("SELECT name FROM nodes WHERE name = ?", (req.venue,))
    exists = cursor.fetchone()
    
    if not exists:
        cursor.execute('''
            INSERT INTO nodes (name, floor, description, occupancy_status, last_verified) 
            VALUES (?, 1, 'Auto-generated via user update', ?, ?)
        ''', (req.venue, req.status, now_str))
    else:
        cursor.execute('''
            UPDATE nodes 
            SET occupancy_status = ?, last_verified = ? 
            WHERE name = ?
        ''', (req.status, now_str, req.venue))
        
    conn.commit()
    conn.close()
    return {"message": "Telemetry verified successfully"}


# ==========================================
# 🗘 ENDPOINT 6: RESET TELEMETRY OVERRIDES
# ==========================================
@app.post("/rooms/reset")
def reset_rooms():
    conn = sqlite3.connect('campus_navigation.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE nodes SET occupancy_status = 'UNVERIFIED', last_verified = 'Never'")
    conn.commit()
    conn.close()
    return {"message": "Telemetry cleared successfully"}


# ==========================================
# 🗺️ ENDPOINT 7: DIJKSTRA GEOGRAPHIC NAVIGATION
# ==========================================
@app.post("/navigate")
def navigate(req: NavigationRequest):
    conn = sqlite3.connect('campus_navigation.db')
    conn.row_factory = sqlite3.Row
    
    nodes = [r['name'] for r in conn.execute("SELECT name FROM nodes").fetchall()]
    edges = conn.execute("SELECT node_from, node_to, distance_meters FROM edges").fetchall()
    conn.close()
    
    if req.start_node not in nodes or req.end_node not in nodes:
        raise HTTPException(status_code=400, detail="Selected points must exist in mapped KML nodes data layer")
        
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