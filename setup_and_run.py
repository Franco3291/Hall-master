import socket
import sqlite3, os, sys, subprocess

# 1. Initialize database tables
print("=== Setting up database ===")
conn = sqlite3.connect('campus_navigation.db')
cur = conn.cursor()

# Create tables if not exist
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

cur.execute('''CREATE TABLE IF NOT EXISTS admin_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_name TEXT NOT NULL,
    admin_password TEXT NOT NULL UNIQUE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')

conn.commit()

# 2. Check if nodes exist, if not seed them
count = cur.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]

# Remove the Vice Chancellors Office everywhere before seeding the map.
cur.execute("DELETE FROM edges WHERE node_from = ? OR node_to = ?", ("Vice chancellors office", "Vice chancellors office"))
cur.execute("DELETE FROM timetable WHERE venue = ?", ("Vice chancellors office",))
cur.execute("DELETE FROM nodes WHERE name = ?", ("Vice chancellors office",))
conn.commit()

count = cur.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
if count == 0:
    print("Seeding campus map nodes...")
    campus_nodes = [
        ("Forensic laboratory", -1.045600, 37.012300, 1, "Main laboratory"),
        ("BS/2", -0.092969, 37.989887, 1, "Common Hub"),
        ("Main Gate Junction", -1.045000, 37.011500, 1, "Main Entry"),
        ("UTC 9", -0.090023, 37.987475, 1, "Lecture"),
        ("STB 2", -0.090755, 37.989205, 1, "Lecture"),
        ("ED 7", -0.090617, 37.989997, 1, "Lecture"),
        ("TC 1", -0.092325, 37.989829, 1, "Lecture"),
        ("Bs/1", -0.092576, 37.990462, 1, "Lecture"),
        ("Hospitality lab", -0.092770, 37.991091, 1, "Lab"),
        ("Forensic laboratory (Old Location)", -0.092555, 37.990695, 1, "Lab"),
        ("Bs/3", -0.093857, 37.991478, 1, "Lecture"),
    ]
    for name, lat, lng, floor, desc in campus_nodes:
        cur.execute("INSERT OR IGNORE INTO nodes (name, floor, description, lat, lng, occupancy_status, last_verified) VALUES (?,?,?,?,?,'UNVERIFIED','Never')", 
                   (name, floor, desc, lat, lng))
    conn.commit()
    print(f"  Added {len(campus_nodes)} nodes")

# 3. Check if timetable exists
tt_count = cur.execute("SELECT COUNT(*) FROM timetable").fetchone()[0]
print(f"Timetable entries: {tt_count}")
print(f"Nodes: {cur.execute('SELECT COUNT(*) FROM nodes').fetchone()[0]}")
print(f"Edges: {cur.execute('SELECT COUNT(*) FROM edges').fetchone()[0]}")

conn.close()
print("\n=== Database ready! ===")

# 4. Start server
print("\nStarting FastAPI server...")
os.environ['ADMIN_PASSWORD'] = 'Campus@123'

def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'

local_ip = get_local_ip()
print(f"\nOpen on this PC: http://127.0.0.1:8000")
print(f"Open on your phone (same WiFi): http://{local_ip}:8000")

subprocess.run([sys.executable, '-m', 'uvicorn', 'main:app', '--reload', '--host', '0.0.0.0', '--port', '8000'])