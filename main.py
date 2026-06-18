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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
# 🧭 ENDPOINT 1: ROOM STATUS
# ==========================================
@app.get("/rooms/status")
def get_room_status():
    with get_db() as conn:
        current_day = datetime.now().strftime('%A')
        current_time = datetime.now().strftime('%H:%M')
        timetable_venues = set()
        for row in conn.execute("SELECT DISTINCT venue FROM timetable WHERE venue IS NOT NULL AND venue != ''").fetchall():
            timetable_venues.add(row['venue'])
        node_rooms = set()
        for row in conn.execute("SELECT name FROM nodes WHERE name IS NOT NULL AND name != ''").fetchall():
            name = row['name']
            if name in timetable_venues:
                node_rooms.add(name)
            elif any(kw in name.lower() for kw in ['hall', 'lab', 'room', 'lecture', 'class', 'office', 'block', 'theatre']):
                node_rooms.add(name)
        all_venue_names = list(timetable_venues | node_rooms)
        rooms_status_feed = []
        for venue_name in all_venue_names:
            if not venue_name:
                continue
            active_class = conn.execute('''SELECT course_code, course_name, end_time FROM timetable
                WHERE venue = ? AND day_of_week = ? AND ? BETWEEN start_time AND end_time LIMIT 1''',
                (venue_name, current_day, current_time)).fetchone()
            override = conn.execute("SELECT occupancy_status, last_verified FROM nodes WHERE name = ?", (venue_name,)).fetchone()
            status = "AVAILABLE"
            schedule_text = "No Class Scheduled Right Now"
            time_verified = "Synced with System Clock"
            if active_class:
                status = "BUSY"
                schedule_text = f"Ongoing: {active_class['course_code']} - {active_class['course_name']} (Ends {active_class['end_time']})"
            else:
                next_class = conn.execute('''SELECT course_code, start_time FROM timetable
                    WHERE venue = ? AND day_of_week = ? AND start_time > ? ORDER BY start_time ASC LIMIT 1''',
                    (venue_name, current_day, current_time)).fetchone()
                if next_class:
                    schedule_text = f"Next class {next_class['course_code']} at {next_class['start_time']}"
            if override and override['occupancy_status'] != 'UNVERIFIED':
                status = override['occupancy_status']
                schedule_text = f"Manual {status} via crowd override."
                time_verified = f"Verified at: {override['last_verified']}"
            rooms_status_feed.append({
                "venue": venue_name, "status": status,
                "current_schedule": schedule_text, "last_verified": time_verified
            })
        return rooms_status_feed

# ==========================================
# 📍 ENDPOINT 2: GEO NODES
# ==========================================
@app.get("/api/geo-nodes")
def get_geo_nodes():
    with get_db() as conn:
        rows = conn.execute("SELECT name, lat, lng, description FROM nodes").fetchall()
        return [{"name": row['name'], "lat": row['lat'], "lng": row['lng'], "description": row['description']} for row in rows]

# ==========================================
# 👤 ENDPOINT 3: STUDENT REGISTRATION / LOGIN
# ==========================================
@app.post("/students/register")
def register_student(req: StudentRegisterRequest):
    with get_db() as conn:
        try:
            conn.execute('''INSERT INTO students (reg_no, password, course, year, semester, units)
                VALUES (?, ?, ?, ?, ?, ?)''', (req.reg_no, req.password, req.course, req.year, req.semester, req.units))
            conn.commit()
            return {"status": "success", "message": "Student registered successfully!"}
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Registration number already exists.")

# --- Smart unit selection: get available units from timetable ---
@app.get("/students/available-units")
def get_available_units(course: str = Query(""), year: int = Query(0), semester: int = Query(0)):
    """
    Returns distinct course codes filtered by course name, year, semester.
    If course is provided, it filters by the program name embedded in course_name/venue.
    """
    with get_db() as conn:
        # Get all timetable entries with their details
        rows = conn.execute('''SELECT DISTINCT course_code, course_name, day_of_week, start_time, end_time, venue 
                               FROM timetable ORDER BY course_code''').fetchall()
        
        # Build a map of unique course codes with their metadata
        seen = {}
        for r in rows:
            code = str(r['course_code']) if r['course_code'] else ""
            name = str(r['course_name']) if r['course_name'] else ""
            venue = str(r['venue']) if r['venue'] else ""
            day = str(r['day_of_week']) if r['day_of_week'] else ""
            
            if not code:
                continue
            
            # Year filter based on first digit of course number
            if year > 0:
                nums = [int(s) for s in code.split() if s.isdigit()]
                if nums:
                    first_digit = int(str(nums[0])[0])
                    if first_digit != year:
                        # Year 1 codes start with 1, year 2 with 2, etc.
                        # But some codes like "CCS 001" don't follow this pattern
                        # Allow codes that share ANY digit with the year
                        if year not in [int(d) for d in str(nums[0])]:
                            continue
            
            # Course filter: if user entered a course name, try to match
            if course:
                course_lower = course.lower()
                # Check if course keywords appear in venue, course_name, or code
                course_keywords = course_lower.split()
                match_found = False
                for kw in course_keywords:
                    if len(kw) < 2:
                        continue
                    if kw in name.lower() or kw in venue.lower() or kw in code.lower():
                        match_found = True
                        break
                # Also check full course name against code prefixes
                # e.g., "Diploma Criminology" -> look for codes starting with DCRM, CRM, etc.
                if not match_found:
                    # Generate acronym from course name (e.g., "Diploma Criminology" -> "DC")
                    words = course_lower.split()
                    acronyms = []
                    for w in words:
                        if len(w) >= 2 and w not in ['of', 'in', 'and', 'the', 'for']:
                            acronyms.append(w[:3].upper())
                    # Check if any timetable venue/code contains our acronyms
                    for ac in acronyms:
                        if ac and (ac in code.upper() or ac in venue.upper()):
                            match_found = True
                            break
                    # Fallback: include the course code if no filtering possible
                    # (shows all units for the year)
                
                if not match_found:
                    # Last try: check if course name appears in page-like venue names
                    # e.g., "CERT.COMM DVPMNT" stored somewhere
                    # For now, skip if no match found
                    continue
            
            if code not in seen:
                seen[code] = {
                    "code": code,
                    "name": name if name and name != code else "",
                    "venue": venue,
                    "day": day
                }
        
        unique = list(seen.values())
        # Sort: prioritize codes that have a venue match for the course
        if course:
            course_lower = course.lower()
            def sort_key(item):
                score = 0
                if course_lower in item['venue'].lower():
                    score += 3
                if course_lower in item['name'].lower():
                    score += 2
                if course_lower in item['code'].lower():
                    score += 1
                return -score
            unique.sort(key=sort_key)
        
        return {"units": unique, "total": len(unique)}

@app.post("/students/login")
def login_student(req: StudentLoginRequest):
    with get_db() as conn:
        student = conn.execute("SELECT reg_no, course, year, semester, units FROM students WHERE reg_no = ? AND password = ?",
            (req.reg_no, req.password)).fetchone()
        if not student:
            raise HTTPException(status_code=401, detail="Invalid registration number or password.")
        return {"reg_no": student['reg_no'], "course": student['course'], "year": student['year'],
                "semester": student['semester'], "units": student['units']}

@app.post("/admin/login")
def login_admin(req: AdminLoginRequest):
    if req.admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    return {"status": "success", "message": "Admin authenticated."}

# ==========================================
# 📅 ENDPOINT 4: STUDENT SCHEDULE
# ==========================================
@app.get("/students/schedule/{reg_no:path}")
def get_student_schedule(reg_no: str):
    with get_db() as conn:
        student = conn.execute("SELECT course, year, semester, units FROM students WHERE reg_no = ?", (reg_no,)).fetchone()
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")
        registered_units = [u.strip() for u in student['units'].split(',') if u.strip()]
        current_day = datetime.now().strftime('%A')
        if not registered_units:
            return {"day": current_day, "student": dict(student), "schedule": []}
        placeholders = ','.join('?' for _ in registered_units)
        query = f'''SELECT course_code, course_name, start_time, end_time, venue FROM timetable
            WHERE UPPER(day_of_week) = UPPER(?) AND (UPPER(course_code) IN ({placeholders}) OR UPPER(venue) IN ({placeholders}))
            ORDER BY start_time ASC'''
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
        return {"day": current_day, "student": {"reg_no": reg_no, "course": student['course'], "year": student['year'],
                "semester": student['semester'], "units": student['units']}, "schedule": schedules}

# ==========================================
# 👥 ENDPOINT 5: VERIFY
# ==========================================
@app.post("/verify")
def verify_room(req: VerificationRequest):
    with get_db() as conn:
        now_str = datetime.now().strftime('%H:%M:%S')
        exists = conn.execute("SELECT name FROM nodes WHERE name = ?", (req.venue,)).fetchone()
        if not exists:
            conn.execute('''INSERT INTO nodes (name, floor, description, occupancy_status, last_verified)
                VALUES (?, 1, 'Auto-generated via user update', ?, ?)''', (req.venue, req.status, now_str))
        else:
            conn.execute("UPDATE nodes SET occupancy_status = ?, last_verified = ? WHERE name = ?", (req.status, now_str, req.venue))
        conn.commit()
    return {"message": "Telemetry verified successfully"}

# ==========================================
# 🗘 ENDPOINT 6: RESET
# ==========================================
@app.post("/rooms/reset")
def reset_rooms():
    with get_db() as conn:
        conn.execute("UPDATE nodes SET occupancy_status = 'UNVERIFIED', last_verified = 'Never'")
        conn.commit()
        return {"message": "Telemetry cleared successfully"}

# ==========================================
# 🗺️ ENDPOINT 7: NAVIGATE
# ==========================================
@app.post("/navigate")
def navigate(req: NavigationRequest):
    with get_db() as conn:
        nodes_data = {r['name']: {"lat": r['lat'], "lng": r['lng']}
                      for r in conn.execute("SELECT name, lat, lng FROM nodes").fetchall()}
        nodes_list = list(nodes_data.keys())
        edges = conn.execute("SELECT node_from, node_to, distance_meters FROM edges").fetchall()
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
        coordinates = []
        for node_name in path:
            node = nodes_data.get(node_name)
            if node and node['lat'] and node['lng']:
                coordinates.append([node['lat'], node['lng']])
        detailed_coords = []
        for i, node_name in enumerate(path):
            node = nodes_data.get(node_name)
            if node and node['lat'] and node['lng']:
                detailed_coords.append([node['lat'], node['lng']])
                if i < len(path) - 1:
                    next_node = nodes_data.get(path[i+1])
                    if next_node and next_node['lat'] and next_node['lng']:
                        detailed_coords.append([(node['lat'] + next_node['lat'])/2, (node['lng'] + next_node['lng'])/2])
        return {"total_distance_meters": round(distances[req.end_node], 1), "routing_path": path,
                "coordinates": detailed_coords if len(detailed_coords) >= 2 else coordinates}

# ============================================================
# 📋 ENDPOINT 8: ADMIN TIMETABLE MANAGEMENT
# ============================================================
@app.post("/admin/timetable/upload-pdf")
async def upload_timetable_pdf(admin_password: str = Form(...), file: UploadFile = File(...)):
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
    TIME_SLOTS_BY_ROW = ["", "08:00-10:00", "10:00-12:00", "12:00-14:00", "14:00-16:00", "16:00-18:00", "18:00-20:00",
                         "08:00-10:00", "10:00-12:00", "12:00-14:00"]
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                table = page.extract_table()
                if not table or len(table) < 2:
                    continue
                num_cols = len(table[0]) if table[0] else 0
                print(f"📋 Page {page_num}: {len(table)} rows x {num_cols} columns")
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
                    print(f"   ⏭️ Skipping page {page_num} (no day headers)")
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
                        start_time, end_time = "08:00", "10:00"
                        if "-" in time_label:
                            parts = time_label.split("-")
                            if len(parts) >= 2:
                                st, et = parts[0].strip(), parts[-1].strip()
                                if ":" in st and ":" in et:
                                    if len(st.split(":")[0]) == 1: st = "0" + st
                                    if len(et.split(":")[0]) == 1: et = "0" + et
                                    start_time, end_time = st, et
                        parsed_classes.append({"course_code": course_code, "course_name": course_code,
                            "day_of_week": day_name, "start_time": start_time, "end_time": end_time, "venue": venue})
                        rows_this_page += 1
                print(f"   ✅ Page {page_num}: +{rows_this_page} entries (total: {len(parsed_classes)})")
                start_idx = len(parsed_classes) - rows_this_page
                for i in range(max(0, start_idx), min(len(parsed_classes), start_idx + 3)):
                    e = parsed_classes[i]
                    print(f"      {e['day_of_week']} {e['start_time']}-{e['end_time']}: {e['course_code']} @ {e['venue']}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {str(e)}")
    if not parsed_classes:
        raise HTTPException(status_code=400, detail="No class data could be extracted.")
    with get_db() as conn:
        conn.execute("DELETE FROM timetable")
        for entry in parsed_classes:
            conn.execute('''INSERT INTO timetable (course_code, course_name, day_of_week, start_time, end_time, venue)
                VALUES (?, ?, ?, ?, ?, ?)''', (entry["course_code"], entry["course_name"], entry["day_of_week"],
                  entry["start_time"], entry["end_time"], entry["venue"]))
        conn.commit()
    return {"status": "success", "message": "Timetable updated successfully!", "classes_imported": len(parsed_classes)}

@app.get("/admin/timetable/all")
def get_all_timetable(admin_password: str = Query(...)):
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    with get_db() as conn:
        rows = conn.execute("SELECT id, course_code, course_name, day_of_week, start_time, end_time, venue FROM timetable ORDER BY day_of_week, start_time").fetchall()
        return [dict(row) for row in rows]

@app.post("/admin/timetable/add")
def add_timetable_entry(admin_password: str = Query(...), entry: TimetableEntry = None):
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    with get_db() as conn:
        conn.execute('''INSERT INTO timetable (course_code, course_name, day_of_week, start_time, end_time, venue)
            VALUES (?, ?, ?, ?, ?, ?)''', (entry.course_code, entry.course_name, entry.day_of_week, entry.start_time, entry.end_time, entry.venue))
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"status": "success", "message": "Entry added!", "id": new_id}

@app.put("/admin/timetable/update/{entry_id}")
def update_timetable_entry(entry_id: int, admin_password: str = Query(...), entry: TimetableEntry = None):
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM timetable WHERE id = ?", (entry_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Entry not found.")
        conn.execute('''UPDATE timetable SET course_code=?, course_name=?, day_of_week=?, start_time=?, end_time=?, venue=? WHERE id=?''',
            (entry.course_code, entry.course_name, entry.day_of_week, entry.start_time, entry.end_time, entry.venue, entry_id))
        conn.commit()
    return {"status": "success", "message": "Entry updated!"}

@app.delete("/admin/timetable/delete/{entry_id}")
def delete_timetable_entry(entry_id: int, admin_password: str = Query(...)):
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM timetable WHERE id = ?", (entry_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Entry not found.")
        conn.execute("DELETE FROM timetable WHERE id = ?", (entry_id,))
        conn.commit()
    return {"status": "success", "message": "Entry deleted!"}

@app.get("/admin/timetable/venues")
def get_all_venues(admin_password: str = Query(...)):
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    with get_db() as conn:
        venues = conn.execute("SELECT DISTINCT venue FROM timetable ORDER BY venue").fetchall()
        return [v["venue"] for v in venues if v["venue"]]

@app.delete("/admin/timetable/clear")
def clear_timetable(admin_password: str = Query(...)):
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    with get_db() as conn:
        conn.execute("DELETE FROM timetable")
        conn.commit()
    return {"status": "success", "message": "All timetable entries cleared!"}

# ============================================================
# 📌 ENDPOINT 9: ADMIN NODE MANAGEMENT
# ============================================================
@app.get("/admin/nodes/all")
def get_all_nodes(admin_password: str = Query(...)):
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    with get_db() as conn:
        rows = conn.execute("SELECT name, lat, lng, floor, description, occupancy_status FROM nodes ORDER BY name").fetchall()
        return [dict(row) for row in rows]

class NodeAddRequest(BaseModel):
    name: str
    lat: float
    lng: float
    floor: int = 1
    description: str = ""

@app.post("/admin/nodes/add")
def add_node(admin_password: str = Query(...), node: NodeAddRequest = None):
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    if not node.name or not node.name.strip():
        raise HTTPException(status_code=400, detail="Node name is required.")
    with get_db() as conn:
        existing = conn.execute("SELECT name FROM nodes WHERE name = ?", (node.name.strip(),)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail=f"Node '{node.name}' already exists.")
        conn.execute('''INSERT INTO nodes (name, floor, description, lat, lng, occupancy_status, last_verified)
            VALUES (?, ?, ?, ?, ?, 'UNVERIFIED', 'Never')''', (node.name.strip(), node.floor, node.description, node.lat, node.lng))
        conn.commit()
    return {"status": "success", "message": f"Node '{node.name}' added!"}

@app.delete("/admin/nodes/delete/{node_name}")
def delete_node(node_name: str, admin_password: str = Query(...)):
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    with get_db() as conn:
        existing = conn.execute("SELECT name FROM nodes WHERE name = ?", (node_name,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found.")
        conn.execute("DELETE FROM edges WHERE node_from = ? OR node_to = ?", (node_name, node_name))
        conn.execute("DELETE FROM nodes WHERE name = ?", (node_name,))
        conn.commit()
    return {"status": "success", "message": f"Node '{node_name}' deleted!"}

@app.put("/admin/nodes/update/{node_name}")
def update_node(node_name: str, admin_password: str = Query(...), node: NodeAddRequest = None):
    if admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    with get_db() as conn:
        existing = conn.execute("SELECT name FROM nodes WHERE name = ?", (node_name,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found.")
        conn.execute("UPDATE nodes SET lat=?, lng=?, floor=?, description=? WHERE name=?",
            (node.lat, node.lng, node.floor, node.description, node_name))
        conn.commit()
    return {"status": "success", "message": f"Node '{node_name}' updated!"}